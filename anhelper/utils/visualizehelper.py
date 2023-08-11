from PIL import Image
import cv2

def imshow(imatbgr):
    if len(imatbgr.shape)==3:
        imat = cv2.cvtColor(imatbgr, cv2.COLOR_BGR2RGB)
    else:
        imat = imatbgr
    img = Image.fromarray(imat)
    display(img)


def drawrect(imat, rect, color=(0,0,255)):
    return cv2.rectangle(imat, rect[:2], rect[2:], color)
    
    
def drawyrect(imat, lmrect, color=(0,0,255)):
    h,w,c = imat.shape
    cp = [w*lmrect[0], h*lmrect[1]]
    wh = [w*lmrect[2], h*lmrect[3]]
    rect = [(int(cp[0]-wh[0]/2), int(cp[1]-wh[1]/2)), (int(cp[0]+wh[0]/2), int(cp[1]+wh[1]/2))]   
    result = cv2.rectangle(imat, *rect, color)
    return result
    
    