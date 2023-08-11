function getpxy(e){
	const px = e.offsetX / e.target.offsetWidth;
	const py = e.offsetY / e.target.offsetHeight;
	return {px:px, py:py};
};

var postaction = (a,x,y)=>{console.log([a,x,y])}
var isdown = false
// action: down, up, move

export default class VTouch{
	constructor(bindobj, callback=(a,x,y)=>{console.log((a,x,y))}){
		//console.log(bindobj)
		bindobj.addEventListener("mousedown", this.mousedown);
		bindobj.addEventListener("mouseup", this.mouseup);
		bindobj.addEventListener("mousemove", this.mousemove);
		bindobj.addEventListener("mouseleave", this.mouseleave);
		postaction = callback
	};
	

	mousedown(e){
		//console.log(this);
		const pxy = getpxy(e);
		isdown = true;
		postaction('down', pxy.px, pxy.py);
		
		//console.log(postaction)
		//const px = e.offsetX / e.target.offsetWidth
		//const py = e.offsetY / e.target.offsetHeight
		//console.log(pxy);
	};
	
	mouseup(e){
		const pxy = getpxy(e);
		isdown = false;
		postaction('up', pxy.px, pxy.py);
	}
	
	mousemove(e){
		if (isdown){
			const pxy = getpxy(e);
			postaction('move', pxy.px, pxy.py);
		}
	}
	
	mouseleave(e){
		if (isdown){
			const pxy = getpxy(e);
			isdown = false
			postaction('up', pxy.px, pxy.py);
		}
	}
	
}