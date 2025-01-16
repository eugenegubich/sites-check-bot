import requests
import dotenv
import os
import paramiko
import json
import re

dotenv.load_dotenv()

def telegram_sendfile(file_path, message, token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {'document': open(file_path, 'rb')}
    data = {"chat_id": chat_id, "caption": message}
    resp = requests.post(url, files=files, data=data)
    return resp.json()

def get_sites_list(server_list, ssh_private_key_file, ssh_user, ssh_port):
    key = paramiko.Ed25519Key.from_private_key_file(ssh_private_key_file)
    sites = []
    
    for server in server_list:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(server)
        print(ssh_port)
        print(ssh_user)
        ssh.connect(server, port=ssh_port, username=ssh_user, pkey=key)
        stdin, stdout, stderr = ssh.exec_command("find /etc/nginx/sites-enabled/ -name '*.conf'")
        config_files = stdout.read().decode().strip().split("\n")
        for config in config_files:
            stdin, stdout, stderr = ssh.exec_command(f'cat {config}')
            config_content = stdout.read().decode()
            matches = re.findall(r"server_name\s+([^\;]+);", config_content)
            for match in matches:
                domains = match.split()
                domains = [domain.lstrip("www.") for domain in domains]
                curritem = {'domain': domains[0], 'server': server}
                sites.append(curritem)
        ssh.close()
    sites_uniq = []
    for site in sites:
        if site not in sites_uniq:
            sites_uniq.append(site)
    return sites_uniq

def check_sites(sites_list, file_path):
    status = []
    for site in sites_list:
        sitename = site['domain']
        server = site['server']
        try:
            r = requests.get('https://' + sitename, timeout=20)
            if r.status_code != 200:
                state = f"HTTP code: {r.status_code}"
                # responce time
                responce_time = r.elapsed.total_seconds()
                status_code = r.status_code
                failed = True
            else:
                state = "OK"
                # responce time
                responce_time = r.elapsed.total_seconds()
                status_code = r.status_code
                failed = False
        except requests.exceptions.RequestException as e:
            state = f"Error: {e}"
            responce_time = 0
            status_code = 0
            failed = True
        
        except Exception as e:
            state = f"Error: {e}"
            responce_time = 0
            status_code = 0
            failed = True
        
        current_status = {"domain": sitename, "state": state, "status_code": status_code, "server": server, "responce_time": responce_time, "failed": failed}
        print(current_status)
        status.append(current_status)
    with open(file_path, "w") as f:
        json.dump(status, f)
        



server_list = os.getenv("SERVER_LIST").strip("[]").replace("'", "").split(",")
server_list = [server.strip() for server in server_list]
sites = get_sites_list(server_list, os.getenv("SSH_PRIVATE_KEY_FILE"), os.getenv("SSH_USER"), os.getenv("SSH_PORT"))
check_sites(sites, os.getenv("RESULT_FILE_PATH"))

