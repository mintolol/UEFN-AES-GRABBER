import asyncio
import aiohttp
import json
import os
import re
import base64

IOS_TOKEN = "NzlhOTMxYjM3NTMzNDU3MGFjMzY5MjM0ZjVkYTA1ZWM6ZWU3MzM1ZGYzYzRhNDEyY2I1NzA1NWFiN2FkZTY5M2U="
SWITCH_TOKEN = "M2Y2OWU1NmM3NjQ5NDkyYzhjYzI5ZjFhZjA4YThhMTI6YjUxZWU5Y2IxMjIzNGY1MGE2OWVmYTY3ZWY1MzgxMmU="
ANDROID_TOKEN = "M2UxM2M1YzU3ZjU5NGE1NzhhYmU1MTZlZWNiNjczZmU6NTMwZTMxNmMzMzdlNDA5ODkzYzU1ZWM0NGYyMmNkNjI="
AUTH_FILE = 'auths.json'

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def save_auth(data):
    with open(AUTH_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_auth():
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, 'r') as f:
            try:
                return json.load(f)
            except: return None
    return None

async def login_flow():
    clear_console()
    print("=== Login Process ===")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token',
                data={'grant_type': 'client_credentials'},
                headers={'Authorization': f'basic {IOS_TOKEN}', 'Content-Type': 'application/x-www-form-urlencoded'}) as resp:
                d = await resp.json()
                if resp.status != 200: 
                    print(f"❌ Login Error (Step 1): {d.get('errorMessage')}")
                    return
                at = d['access_token']

            async with session.post('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/deviceAuthorization',
                data={'prompt': 'login'},
                headers={'Authorization': f'bearer {at}', 'Content-Type': 'application/x-www-form-urlencoded'}) as resp:
                d = await resp.json()
                v_uri, d_code, expires_in, interval = d['verification_uri_complete'], d['device_code'], d['expires_in'], d['interval']

            print(f"\n🔗 Please open the following URL in your browser and approve it.：\n{v_uri}\n")
            print("Pending approval...")
            token = None
            for _ in range(int(expires_in / interval)):
                await asyncio.sleep(interval)
                async with session.post('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token',
                    data={'grant_type': 'device_code', 'device_code': d_code},
                    headers={'Authorization': f'basic {IOS_TOKEN}', 'Content-Type': 'application/x-www-form-urlencoded'}) as pr:
                    pd = await pr.json()
                    if pr.status == 200:
                        token = pd
                        break
                    elif pd.get('errorCode') != 'errors.com.epicgames.account.oauth.authorization_pending':
                        break
            
            if not token:
                print("❌ A timeout or error occurred.")
                return

            async with session.get('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/exchange', 
                                   headers={'Authorization': f"bearer {token['access_token']}"}) as er:
                ed = await er.json()
            
            async with session.post('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token', 
                data={'grant_type': 'exchange_code', 'exchange_code': ed['code']}, 
                headers={'Authorization': f"basic {SWITCH_TOKEN}", 'Content-Type': 'application/x-www-form-urlencoded'}) as fr:
                fd = await fr.json()

            acc_id = token.get('account_id') or token.get('accountId')
            async with session.post(f"https://account-public-service-prod.ol.epicgames.com/account/api/public/account/{acc_id}/deviceAuth", 
                                    json={}, 
                                    headers={'Authorization': f"bearer {fd['access_token']}"}) as ar:
                ad = await ar.json()
            
            if 'deviceId' not in ad:
                print(f"❌ DeviceAuth creation error: {ad}")
                return

            save_auth({
                "accountId": acc_id,
                "deviceId": ad['deviceId'],
                "secret": ad['secret'],
                "displayName": token.get('displayName', 'Unknown')
            })
            print(f"\n✅ Login successful.: {token.get('displayName')}")
            
        except Exception as e:
            print(f"⚠️ Login Error: {e}")
        finally:
            input("\nPress the Enter key to return to the menu...")

async def get_key_flow(map_code):
    clear_console()
    print(f"=== Fetching AES Key for: {map_code} ===")
    user_auth = get_auth()
    if not user_auth:
        print("❌ Please log in first.")
        input("\nPress the Enter key to return to the menu...")
        return

    async with aiohttp.ClientSession() as session:
        try:
            payload = {
                'grant_type': 'device_auth',
                'account_id': user_auth['accountId'],
                'device_id': user_auth['deviceId'],
                'secret': user_auth['secret'],
                'token_type': 'eg1'
            }
            async with session.post('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token', 
                                    data=payload, 
                                    headers={'Authorization': f'basic {SWITCH_TOKEN}', 'Content-Type': 'application/x-www-form-urlencoded'}) as resp:
                token_data = await resp.json()
                if resp.status != 200:
                    print(f"❌ Token Error. You need to log in again. {token_data}")
                    return
                
                saved_access_token = token_data['access_token']

                async with session.get('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/exchange', 
                                       headers={'Authorization': f'Bearer {saved_access_token}'}) as er:
                    ed = await er.json()
                
                async with session.post('https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token',
                                        data={'grant_type': 'exchange_code', 'exchange_code': ed['code']},
                                        headers={'Authorization': f'basic {ANDROID_TOKEN}', 'Content-Type': 'application/x-www-form-urlencoded'}) as fr:
                    fd = await fr.json()
                    final_access_token = fd['access_token']
            async with session.get("https://export-service-new.dillyapis.com/v1/mappings") as resp:
                mappings_data = await resp.json()
                version_str = mappings_data.get("version", "")
                match = re.search(r'Release-(\d+)\.(\d+)-CL-(\d+)', version_str)
                if not match: raise Exception(f"Failed to parse version: {version_str}")
                major, minor, cl = match.groups()
            content_url = f"https://content-service.bfda.live.use1a.on.epicgames.com/api/content/v4/cooked-content-package/link/{map_code}"
            params = {"role": "client", "platform": "windows", "major": major, "minor": minor, "patch": cl}
            headers = {"Authorization": f"bearer {final_access_token}"}
            
            async with session.get(content_url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    err_data = await resp.json()
                    if err_data.get('errorCode') == "errors.com.epicgames.content-service.unexpected_link_type":
                        print("⚠️ The 1.0 map is not encrypted.")
                    else:
                        print(f"❌ Error: {err_data}")
                    return
                
                content_data = await resp.json()

                if content_data.get("isEncrypted"):
                    root = content_data.get("resolved", {}).get("root", {})
                    key_payload = [{"moduleId": root.get("moduleId"), "version": root.get("version")}]
                    async with session.post("https://content-service.bfda.live.use1a.on.epicgames.com/api/content/v4/module/key/batch",
                                            json=key_payload,
                                            headers={"Authorization": f"bearer {final_access_token}", "Content-Type": "application/json"}) as k_resp:
                        key_results = await k_resp.json()
                        
                        if isinstance(key_results, list) and len(key_results) > 0:
                            key_info = key_results[0].get("key", {})
                            aes_hex = "0x" + base64.b64decode(key_info.get("Key")).hex().upper()
                            print(f"\n🔑 Successful acquisition of AES key")
                            print(f"Map Code: {map_code}")
                            print(f"AES Key: {aes_hex}")
                            print(f"GUID: {key_info.get('Guid')}\n")
                        else:
                            print(f"❌ AES Key not found.: {key_results}")
                else:
                    print("ℹ️ This map is not encrypted.")

        except Exception as e:
            print(f"⚠️ Error: {e}")
        finally:
            input("\nPress the Enter key to return to the menu...")

async def main():
    while True:
        clear_console()
        print("="*35)
        print("   UEFN AES GRABBER")
        print("="*35)
        print("1: Login")
        print("2: AES Key Retrieval")
        print("q: Exit")
        print("-" * 35)
        choice = input("Choose > ").strip().lower()

        if choice == '1':
            await login_flow()
        elif choice == '2':
            m_code = input("\nEnter the MapCode > ").strip()
            if m_code:
                await get_key_flow(m_code)
            else:
                print("❌ Please enter the MapCode")
                await asyncio.sleep(1.5)
        elif choice == 'q':
            print("Exiting the program.")
            break
        else:
            print("❌ Invalid selection.")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())