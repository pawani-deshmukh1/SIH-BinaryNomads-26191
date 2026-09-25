import asyncio
from playwright.async_api import async_playwright

async def audit_with_chromium():
    print("\n" + "="*60)
    print(">>> PLAYWRIGHT CHROMIUM AUDIT: BYPASSING BOT PROTECTION <<<")
    print("="*60 + "\n")
    
    endpoints = [
        {"name": "NDEM (National Hazard Zonation)", "url": "https://ndem.ndma.gov.in/"},
        {"name": "ASDMA (Assam State Disaster Data)", "url": "https://asdma.assam.gov.in/"},
        {"name": "India WRIS / NWIC", "url": "https://indiawris.gov.in/wris/"},
        {"name": "MOSDAC (ISRO Raw Satellite Data)", "url": "https://mosdac.gov.in/"},
        {"name": "IMD (Doppler Weather Radar)", "url": "https://mausam.imd.gov.in/"},
        {"name": "NESAC FLEWS", "url": "https://nesac.gov.in/flews/"},
        {"name": "PM Gati Shakti", "url": "https://gatishakti.gov.in/"}
    ]

    async with async_playwright() as p:
        # Launching with standard user agent to avoid bot detection
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        for ep in endpoints:
            print(f"Testing: {ep['name']}")
            print(f"Target : {ep['url']}")
            page = await context.new_page()
            try:
                # Wait until network is mostly idle to bypass splash screens
                response = await page.goto(ep['url'], timeout=15000, wait_until="domcontentloaded")
                
                if response:
                    status = response.status
                    if status == 200:
                        # Check if it's just a Captcha/Cloudflare page despite 200 OK
                        title = await page.title()
                        if "Just a moment" in title or "Attention Required" in title:
                            print(f"Status : \033[93mBlocked by Cloudflare/Captcha (Title: {title})\033[0m\n")
                        else:
                            print(f"Status : \033[92m200 OK (Accessible via Browser!) - Title: {title}\033[0m\n")
                    elif status in [401, 403]:
                        print(f"Status : \033[91m{status} Forbidden (Hard block / VPN required)\033[0m\n")
                    else:
                        print(f"Status : \033[93m{status} (Unexpected response)\033[0m\n")
                else:
                    print(f"Status : \033[91mNo Response (Connection dropped by server)\033[0m\n")
                    
            except Exception as e:
                err_msg = str(e).split('\\n')[0]
                print(f"Status : \033[91mTimeout / Connection Refused ({err_msg})\033[0m\n")
            finally:
                await page.close()
                
        await browser.close()
        
    print("="*60)
    print("CHROMIUM AUDIT COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(audit_with_chromium())
