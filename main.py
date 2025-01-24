import requests
import dotenv
import os
import paramiko
import json
import re
import aiohttp
import asyncio
import datetime
from io import BytesIO

dotenv.load_dotenv()

def telegram_sendfile(file, message, token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {'document': file}
    data = {"chat_id": chat_id, "caption": message}
    resp = requests.post(url, files=files, data=data)
    return resp.json()

def get_sites_list(server_list, ssh_private_key_file, ssh_user, ssh_port):
    key = paramiko.Ed25519Key.from_private_key_file(ssh_private_key_file)
    sites = []
    
    for server in server_list:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server, port=ssh_port, username=ssh_user, pkey=key)
        stdin, stdout, stderr = ssh.exec_command("find /etc/nginx/sites-enabled/ -name '*.conf'")
        config_files = stdout.read().decode().strip().split("\n")
        for config in config_files:
            stdin, stdout, stderr = ssh.exec_command(f'cat {config}')
            config_content = stdout.read().decode()
            matches = re.findall(r"server_name\s+([^\;]+);", config_content)
            for match in matches:
                domains = match.split()
                domains = [domain.removeprefix("www.") for domain in domains]
                curritem = {'domain': domains[0], 'server': server}
                sites.append(curritem)
        ssh.close()
    sites_uniq = []
    for site in sites:
        if site not in sites_uniq:
            sites_uniq.append(site)
    return sites_uniq

async def fetch_status(session, site, semaphore, retries):
    sitename = site['domain']
    server = site['server']
    async with semaphore:
        attempts = 0
        while attempts < retries:
            try:
                async with session.get(f'https://{sitename}', timeout=20) as response:
                    responce_time = response.elapsed.total_seconds() if hasattr(response, 'elapsed') else 0
                    if response.status != 200: 
                        attempts += 1
                        if attempts >= retries:
                            state = f"HTTP code: {response.status}"
                            failed = True
                        else:
                            await asyncio.sleep(3)
                    else:
                        state = "OK"
                        failed = False
                    return {"domain": sitename, "state": state, "status_code": response.status, "server": server, "responce_time": responce_time, "failed": failed}
            except asyncio.exceptions.TimeoutError:
                attempts += 1
                if attempts >= retries:
                    return {"domain": sitename, "state": "Timeout", "status_code": 0, "server": server, "responce_time": 0, "failed": True}
                else:
                    await asyncio.sleep(3)
            except aiohttp.ClientConnectionError:
                attempts += 1
                if attempts >= retries:
                    return {"domain": sitename, "state": "Connection Error", "status_code": 0, "server": server, "responce_time": 0, "failed": True}
                else:
                    await asyncio.sleep(3)
            except aiohttp.ClientError as e:
                attempts += 1
                if attempts >= retries:
                    return {"domain": sitename, "state": f"Error: {e}", "status_code": 0, "server": server, "responce_time": 0, "failed": True}
                else:
                    await asyncio.sleep(3)
            except Exception as e:
                attempts += 1
                if attempts >= retries:
                    return {"domain": sitename, "state": f"Error: {e}", "status_code": 0, "server": server, "responce_time": 0, "failed": True}
                else:
                    await asyncio.sleep(3)

async def check_sites_async(sites_list, max_concurrent_requests=100):
    status = []
    semaphore = asyncio.Semaphore(max_concurrent_requests)
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_status(session, site, semaphore, int(os.getenv("RETRIES"))) for site in sites_list]
        status = await asyncio.gather(*tasks)
    return status

        
def count_server_errors(requests_status):
    servers_status = []
    for site in requests_status:
        server = site['server']
        if not any(server in d['server'] for d in servers_status):
            servers_status.append({'server': server, 'errors': 0, 'working_sites': 0})
        if site['failed']:
            for server_status in servers_status:
                if server_status['server'] == server:
                    server_status['errors'] += 1
        else:
            for server_status in servers_status:
                if server_status['server'] == server:
                    server_status['working_sites'] += 1
    message = ""
    for server in servers_status:
        message += f"Server: {server['server']}\nErrors: {server['errors']}\nWorking sites: {server['working_sites']}\n\n"
    return message




server_list = os.getenv("SERVER_LIST").strip("[]").replace("'", "").split(",")
server_list = [server.strip() for server in server_list]
sites = get_sites_list(server_list, os.getenv("SSH_PRIVATE_KEY_FILE"), os.getenv("SSH_USER"), os.getenv("SSH_PORT"))
check_result = asyncio.run(check_sites_async(sites, int(os.getenv("PARRALLEL"))))
file_obj = BytesIO(json.dumps(check_result, indent=4).encode())
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
file_obj.name = f'{os.getenv("RESULT_FILE_PREFIX")}_{timestamp}.json'
message = count_server_errors(check_result)
telegram_sendfile(file_obj, message, os.getenv("TELEGRAM_API_KEY"), os.getenv("TELEGRAM_CHAT_ID"))

