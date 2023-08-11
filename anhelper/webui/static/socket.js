export default class Socket{
	constructor(url){
		this.url = url;	
		this.onreceive = msg=>{console.log(msg)};
		this.ws = null;
		this.connected = false;
	}
	sendonconnect = null
	//ws = null;
	
	connect(){
		if (!window.WebSocket){
			return console.log('浏览器不支持WebSocket')
		}
		this.connected = null
		this.ws = new WebSocket(this.url)

		this.ws.onopen = () =>{
			this.connected = true
			if (this.sendonconnect!=null){
				this.ws.send(this.sendonconnect)
				this.sendonconnect = null
			}
			//console.log(this)
		}
		
		this.ws.onclose = () =>{
			this.connected = false
			console.log('socket closed')
		}
		this.ws.onmessage = msg =>{
			this.onreceive(msg.data)
		}
	}
	
	send(msg){
		if (this.connected==false){
			this.connect()
		}
		if (this.connected==null){
			this.sendonconnect = msg
		}else{
			try{
				this.ws.send(msg)
			}catch (e){
				console.log('发送失败')
				console.log(msg)
			}
		}
	}
	
	close(){
		this.ws.close()
	}
	
}