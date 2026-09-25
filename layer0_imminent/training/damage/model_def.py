"""
Siamese ResNet50 U-Net -- 3-class building damage assessment.
Architecture derived directly from checkpoint weight shapes:
  Block 0: in=6144 (layer4_pre+layer4_post=4096 + layer3_pre+layer3_post=2048)
  Block 1: in=1536 (512 + layer2_pre+layer2_post=1024)
  Block 2: in=768  (256 + layer1_pre+layer1_post=512)
  Block 3: in=256  (128 + stem_pre+stem_post=128, stem=64-ch per branch)
  Block 4: in=64   (no skip)
  head.0 : [3, 32, 3, 3] kernel -> Conv2d(32, 3, 3, padding=1)

Input:  two separate [1, 3, H, W] tensors (pre, post)
Output: [1, 3, H, W] logits  (softmax -> per-class probability map)
"""

import torch
import torch.nn as nn
import torchvision.models as tvm
import torch.nn.functional as F


class ConvBnRelu(nn.Sequential):
    def __init__(self, in_ch, out_ch, kernel=3, stride=1, padding=1):
        super().__init__(
            nn.Conv2d(in_ch, out_ch, kernel, stride, padding, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )


class DecoderBlock(nn.Module):
    """UNet decoder block: bilinear upsample + optional skip-concat + 2x ConvBnRelu."""

    def __init__(self, in_ch, out_ch):
        """
        in_ch: total channels AFTER concatenating skip (caller pre-computes this)
        out_ch: output channels
        """
        super().__init__()
        self.conv1 = ConvBnRelu(in_ch, out_ch)
        self.conv2 = ConvBnRelu(out_ch, out_ch)

    def forward(self, x, skip=None):
        x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        if skip is not None:
            x = torch.cat([x, skip], dim=1)
        return self.conv2(self.conv1(x))


class ResNet50Encoder(nn.Module):
    """
    ResNet50 backbone. Exposes:
      stem (64-ch after maxpool, before layer1)
      layer1 (256-ch), layer2 (512-ch), layer3 (1024-ch), layer4 (2048-ch)
    """
    def __init__(self):
        super().__init__()
        base = tvm.resnet50(weights=None)
        self.conv1   = base.conv1
        self.bn1     = base.bn1
        self.relu    = base.relu
        self.maxpool = base.maxpool
        self.layer1  = base.layer1
        self.layer2  = base.layer2
        self.layer3  = base.layer3
        self.layer4  = base.layer4

    def forward(self, x):
        s = self.maxpool(self.relu(self.bn1(self.conv1(x))))  # 64-ch stem
        x1 = self.layer1(s)    # 256-ch
        x2 = self.layer2(x1)   # 512-ch
        x3 = self.layer3(x2)   # 1024-ch
        x4 = self.layer4(x3)   # 2048-ch
        return s, x1, x2, x3, x4


class SiameseResNet50UNet(nn.Module):
    """
    Siamese architecture with TWO INDEPENDENT ResNet50 encoders.
    Named encoder_pre / encoder_post to match checkpoint keys.

    Skip connections concatenate pre+post features at each scale.
    Block channel computation (derived from checkpoint weight shapes):
      Block 0: cat(layer4_pre, layer4_post, layer3_pre, layer3_post) = 4096+2048 = 6144 -> 512
      Block 1: cat(out0_up, layer2_pre, layer2_post) = 512+1024 = 1536 -> 256
      Block 2: cat(out1_up, layer1_pre, layer1_post) = 256+512  =  768 -> 128
      Block 3: cat(out2_up, stem_pre, stem_post)     = 128+64+64 = 256 -> 64
      Block 4: upsample only                          = 64             -> 32
      head  : Conv2d(32, 3, kernel_size=3, padding=1)
    """

    NUM_CLASSES = 3  # 0=no-damage, 1=minor, 2=destroyed

    def __init__(self):
        super().__init__()
        self.encoder_pre  = ResNet50Encoder()
        self.encoder_post = ResNet50Encoder()

        self.decoder = nn.ModuleDict({
            "blocks": nn.ModuleList([
                DecoderBlock(6144, 512),   # block 0
                DecoderBlock(1536, 256),   # block 1
                DecoderBlock( 768, 128),   # block 2
                DecoderBlock( 256,  64),   # block 3  (skip = stem_pre + stem_post = 128)
                DecoderBlock(  64,  32),   # block 4  (no skip)
            ])
        })

        self.head = nn.Sequential(
            nn.Conv2d(32, self.NUM_CLASSES, kernel_size=3, padding=1),
        )

    def forward(self, pre: torch.Tensor, post: torch.Tensor):
        """
        pre, post : [B, 3, H, W]
        returns   : [B, NUM_CLASSES, H, W]  (raw logits)
        """
        ps, p1, p2, p3, p4 = self.encoder_pre(pre)
        qs, q1, q2, q3, q4 = self.encoder_post(post)

        blocks = self.decoder["blocks"]

        # Block 0: upsample layer4 to layer3 spatial size, cat all four feature maps
        x = torch.cat([p4, q4], dim=1)             # 4096-ch at layer4 resolution
        s0 = torch.cat([p3, q3], dim=1)            # 2048-ch at layer3 resolution
        x = F.interpolate(x, size=s0.shape[2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, s0], dim=1)              # 4096+2048 = 6144
        x = blocks[0].conv2(blocks[0].conv1(x))    # -> 512

        # Block 1: upsample to layer2 size, cat
        s1 = torch.cat([p2, q2], dim=1)            # 1024-ch
        x = F.interpolate(x, size=s1.shape[2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, s1], dim=1)              # 512+1024 = 1536
        x = blocks[1].conv2(blocks[1].conv1(x))    # -> 256

        # Block 2: upsample to layer1 size, cat
        s2 = torch.cat([p1, q1], dim=1)            # 512-ch
        x = F.interpolate(x, size=s2.shape[2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, s2], dim=1)              # 256+512 = 768
        x = blocks[2].conv2(blocks[2].conv1(x))    # -> 128

        # Block 3: upsample to stem size, cat
        s3 = torch.cat([ps, qs], dim=1)            # 128-ch stem (64+64)
        x = F.interpolate(x, size=s3.shape[2:], mode="bilinear", align_corners=False)
        x = torch.cat([x, s3], dim=1)              # 128+128 = 256
        x = blocks[3].conv2(blocks[3].conv1(x))    # -> 64

        # Block 4: upsample to input size, no skip
        x = F.interpolate(x, size=pre.shape[2:], mode="bilinear", align_corners=False)
        x = blocks[4].conv2(blocks[4].conv1(x))    # -> 32

        return self.head(x)
