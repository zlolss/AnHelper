if __name__ == "__main__":
    print("init server")
    from .server import AnhelperServer
    serv = AnhelperServer()
    serv.start()
    print("server start")
    serv.join()
    print("server closed")
    exit(0)
    pass