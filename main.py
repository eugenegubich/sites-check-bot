import requests
import dotenv
import os
import paramiko
import json

dotenv.load_dotenv()

def telegram_sendfile(file_path, message, token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {'document': open(file_path, 'rb')}
    data = {"chat_id": chat_id, "caption": message}
    resp = requests.post(url, files=files, data=data)
    return resp.json()

def get_sites_list(server_list, ssh_private_key_file, ssh_user, ssh_port): # Get the list of sites from the server and return json
    sites = {}
    key = paramiko.RSAKey.from_private_key_file(ssh_private_key_file)

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
                server_domains.extend(domains)

        sites[server] = list(set(server_domains))

        ssh.close()
    return sites

def main():
    get_sites_list(os.getenv("SERVER_LIST"), os.getenv("SSH_PRIVATE_KEY_FILE"), os.getenv("SSH_USER"), os.getenv("SSH_PORT"))



