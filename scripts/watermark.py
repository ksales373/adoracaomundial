import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
LOGO=Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','img','569f690325138fc4db2591a39b664b30.png')).convert('RGBA')
FONT='/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
def mark(src, dst):
    im=Image.open(src).convert('RGB'); W,H=im.size
    s=min(W,H)
    lh=max(28,int(s*0.075))                 # logo height
    pad=int(s*0.03)
    f=ImageFont.truetype(FONT,max(12,int(lh*0.36)))
    f2=ImageFont.truetype(FONT.replace('Bold','Medium'),max(9,int(lh*0.24)))
    t1,t2='ADORAÇÃO MUNDIAL','SOUTH RIVER · MEDIA'
    d0=ImageDraw.Draw(im)
    tw=max(d0.textlength(t1,font=f),d0.textlength(t2,font=f2))
    bw=int(lh+lh*0.25+tw); bh=lh
    layer=Image.new('RGBA',im.size,(0,0,0,0))
    x=W-pad-bw; y=H-pad-bh
    lg=LOGO.resize((lh,lh),Image.LANCZOS)
    a=lg.split()[3].point(lambda v:int(v*0.85)); lg.putalpha(a)
    layer.paste(lg,(x,y),lg)
    d=ImageDraw.Draw(layer)
    tx=x+lh+int(lh*0.25)
    d.text((tx,y+int(lh*0.08)),t1,font=f,fill=(255,255,255,215))
    d.text((tx,y+int(lh*0.56)),t2,font=f2,fill=(255,255,255,190))
    # soft shadow so it reads on light walls
    sh=Image.new('RGBA',im.size,(0,0,0,0)); sh.putalpha(layer.split()[3].point(lambda v:int(v*0.55)))
    sh=sh.filter(ImageFilter.GaussianBlur(max(2,lh//14)))
    out=Image.alpha_composite(Image.alpha_composite(im.convert('RGBA'),sh),layer).convert('RGB')
    out.save(dst,quality=88,optimize=True,progressive=True)
if __name__=='__main__':
    mark(sys.argv[1],sys.argv[2])
