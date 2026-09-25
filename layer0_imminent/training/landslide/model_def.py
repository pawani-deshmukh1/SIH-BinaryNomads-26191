"""
Monolith ResNet50 U-Net -- binary landslide segmentation.
Architecture derived directly from checkpoint weight shapes:
  Block 0: conv1.in=3072 (layer4=2048 + layer3=1024)  -> 256
  Block 1: conv1.in=768  (256 + layer2=512)            -> 128
  Block 2: conv1.in=384  (128 + layer1=256)            -> 64
  Block 3: conv1.in=128  (64  + stem=64)               -> 32
  Block 4: conv1.in=32   (no skip)                     -> 16
  seg_head: [1, 16, 3, 3] -> Conv2d(16, 1, kernel_size=3, padding=1)

Input:  [1, 3, 512, 512]
Output: [1, 1, H, W] logits  (sigmoid -> landslide probability per pixel)
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
    """UNet decoder block. Caller passes pre-concatenated tensor."""
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv1 = ConvBnRelu(in_ch, out_ch)
        self.conv2 = ConvBnRelu(out_ch, out_ch)

    def forward(self, x):
        return self.conv2(self.conv1(x))


class ResNet50Backbone(nn.Module):
    """ResNet50 backbone named to match checkpoint prefix 'encoder.*'."""
    def __init__(self):
        super().__init__()
        base = tvm.resnet50(weights=None)
        self.conv1   = base.conv1
        self.bn1     = base.bn1
        self.relu    = base.relu
        self.maxpool = base.maxpool
        self.layer1  = base.layer1   # 256-ch
        self.layer2  = base.layer2   # 512-ch
        self.layer3  = base.layer3   # 1024-ch
        self.layer4  = base.layer4   # 2048-ch

    def forward(self, x):
        s  = self.maxpool(self.relu(self.bn1(self.conv1(x))))  # 64-ch stem
        x1 = self.layer1(s)
        x2 = self.layer2(x1)
        x3 = self.layer3(x2)
        x4 = self.layer4(x3)
        return s, x1, x2, x3, x4


class MonolithLandslideUNet(nn.Module):
    """Single-encoder ResNet50 UNet for binary landslide segmentation."""

    def __init__(self):
        super().__init__()
        self.encoder = ResNet50Backbone()

        # Naming: decoder.blocks.N.* to match checkpoint keys exactly
        self.decoder = nn.ModuleDict({
            "blocks": nn.ModuleList([
                DecoderBlock(3072, 256),   # block 0: layer4 + layer3 skip
                DecoderBlock( 768, 128),   # block 1: 256 + layer2
                DecoderBlock( 384,  64),   # block 2: 128 + layer1
                DecoderBlock( 128,  32),   # block 3: 64  + stem
                DecoderBlock(  32,  16),   # block 4: no skip
            ])
        })

        # segmentation_head.0 -> Conv2d(16, 1, kernel_size=3, padding=1)
        self.segmentation_head = nn.Sequential(
            nn.Conv2d(16, 1, kernel_size=3, padding=1),
        )

    def forward(self, x: torch.Tensor):
        """x: [B, 3, H, W]  ->  [B, 1, H, W] logits"""
        stem, x1, x2, x3, x4 = self.encoder(x)
        blocks = self.decoder["blocks"]

        # Block 0: upsample layer4 to match layer3 spatial size, then cat and decode
        f = F.interpolate(x4, size=x3.shape[2:], mode="bilinear", align_corners=False)
        f = torch.cat([f, x3], dim=1)              # 2048+1024=3072
        f = blocks[0](f)                            # -> 256

        # Block 1: upsample to match layer2 spatial size, cat
        f = F.interpolate(f, size=x2.shape[2:], mode="bilinear", align_corners=False)
        f = torch.cat([f, x2], dim=1)              # 256+512=768
        f = blocks[1](f)                            # -> 128

        # Block 2: upsample to match layer1 spatial size, cat
        f = F.interpolate(f, size=x1.shape[2:], mode="bilinear", align_corners=False)
        f = torch.cat([f, x1], dim=1)              # 128+256=384
        f = blocks[2](f)                            # -> 64

        # Block 3: upsample to match stem spatial size, cat
        f = F.interpolate(f, size=stem.shape[2:], mode="bilinear", align_corners=False)
        f = torch.cat([f, stem], dim=1)             # 64+64=128
        f = blocks[3](f)                            # -> 32

        # Block 4: upsample to input size, no skip
        f = F.interpolate(f, size=x.shape[2:], mode="bilinear", align_corners=False)
        f = blocks[4](f)                            # -> 16

        return self.segmentation_head(f)
