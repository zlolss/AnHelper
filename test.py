from anhelper.webui import WebUI
import webbrowser

def main():
    ui = WebUI()
    ui.start()
    webbrowser.open(ui.url, new=0, autoraise=True)

if __name__=='__main__':
    main()