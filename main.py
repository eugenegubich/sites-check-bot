import requests
import dotenv
import os
import paramiko
import json
import re
import whois
import datetime

dotenv.load_dotenv()

def telegram_sendfile(file_path, message, token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {'document': open(file_path, 'rb')}
    data = {"chat_id": chat_id, "caption": message}
    resp = requests.post(url, files=files, data=data)
    return resp.json()

def get_domain_expiration_date(domain):
    try:
        w = whois.whois(domain)
        expiration_date = w.expiration_date
        if expiration_date:
            return expiration_date
        else:
            return "No data"
    except Exception:
        return "No data"

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
        except requests.exceptions.Timeout:
            state = "Timeout"
            responce_time = 0
            status_code = 0
            failed = True
        except requests.exceptions.ConnectionError:
            state = "Connection Error"
            responce_time = 0
            status_code = 0
            failed = True
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
        
        domain_expire = get_domain_expiration_date(sitename)
        
        current_status = {"domain": sitename, "state": state, "status_code": status_code, "server": server, "responce_time": responce_time, "failed": failed, "domain_expire": domain_expire}
        status.append(current_status)
    with open(file_path, "w") as f:
        json.dump(status, f)
    return status

        
def count_server_errors(requests_status):
    servers_status = []
    for site in requests_status:
        server = site['server']
        if not any(server in d['server'] for d in servers_status):
            servers_status.append({'server': server, 'errors': 0, 'working_sites': 0, 'expired_domains': 0, 'no_data_domains': 0})
        if site['failed']:
            for server_status in servers_status:
                if server_status['server'] == server:
                    server_status['errors'] += 1
        else:
            for server_status in servers_status:
                if server_status['server'] == server:
                    server_status['working_sites'] += 1
        if site['domain_expire'] != "No data":
            for server_status in servers_status:
                if server_status['server'] == server:
                    expire_date = datetime.datetime.strptime(site['domain_expire'], "%Y-%m-%d")
                    if expire_date < datetime.datetime.now():
                        server_status['expired_domains'] += 1
        else:
            for server_status in servers_status:
                if server_status['server'] == server:
                    server_status['no_data_domains'] += 1

                
    message = ""
    for server in servers_status:
        message += f"Server: {server['server']}\nErrors: {server['errors']}\nWorking sites: {server['working_sites']}\nExpired domains: {server['expired_domains']}\nNo data domains: {server['no_data_domains']}\n\n"
    return message




server_list = os.getenv("SERVER_LIST").strip("[]").replace("'", "").split(",")
server_list = [server.strip() for server in server_list]
sites = get_sites_list(server_list, os.getenv("SSH_PRIVATE_KEY_FILE"), os.getenv("SSH_USER"), os.getenv("SSH_PORT"))
check_result = check_sites(sites, os.getenv("RESULT_FILE_PATH"))
message = count_server_errors(check_result)
print(message)


