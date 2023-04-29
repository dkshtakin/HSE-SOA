import socket

def main():
    proxy_addr = '0.0.0.0'
    proxy_port = 8080
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        while True:
            req = input()
            try:
                s.sendto(req.encode(), (proxy_addr, proxy_port))
                res, _ = s.recvfrom(1024)
                print(res.decode(), end='')
            except Exception as e:
                print(e)


if __name__ == '__main__':
    main()
