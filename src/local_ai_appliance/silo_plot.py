"""Small offline PNG bar chart writer; standard library only.

This source ships with the pinned toolchain; no task-time plotting downloads.
"""
import math
import struct
import zlib

FONT={
 '0':['111','101','101','101','111'],'1':['010','110','010','010','111'],
 '2':['111','001','111','100','111'],'3':['111','001','111','001','111'],
 '4':['101','101','111','001','001'],'5':['111','100','111','001','111'],
 '6':['111','100','111','101','111'],'7':['111','001','010','010','010'],
 '8':['111','101','111','101','111'],'9':['111','101','111','001','111'],
 'S':['111','100','111','001','111'],'Y':['101','101','010','010','010'],
 'N':['101','111','111','111','101'],'K':['101','110','100','110','101'],
 'G':['111','100','101','101','111'],'-':['000','000','111','000','000'],
 '.':['000','000','000','000','010'],' ':['000']*5,
}


def bar_chart(labels,values):
    if not isinstance(labels,(tuple,list)) or not isinstance(values,(tuple,list)) or not 1<=len(labels)==len(values)<=8:
        raise ValueError('Supply 1–8 labels and values')
    if any(not isinstance(s,str) or len(s)>12 for s in labels) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in values):
        raise ValueError('Use bounded labels and finite nonnegative values')
    width,height=640,360
    pixels=bytearray(b'\xff'*(width*height*3))
    def rect(x,y,w,h,color):
        for row in range(max(0,y),min(height,y+h)):
            for col in range(max(0,x),min(width,x+w)):
                start=3*(row*width+col); pixels[start:start+3]=bytes(color)
    def text(value,x,y):
        for letter in value.upper():
            for row,bits in enumerate(FONT.get(letter,FONT[' '])):
                for col,bit in enumerate(bits):
                    if bit=='1': rect(x+col*3,y+row*3,3,3,(20,25,35))
            x+=12
    rect(48,32,2,268,(30,35,45)); rect(48,300,560,2,(30,35,45))
    scale=max(values) or 1; step=540//len(labels)
    for index,(label,value) in enumerate(zip(labels,values)):
        h=round(value/scale*220); x=60+index*step
        rect(x,300-h,min(110,step-20),h,(35,110,180))
        text(f'{value:g} KG',x,max(10,278-h)); text(label,x,315)
    def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw=b''.join(b'\0'+bytes(pixels[y*width*3:(y+1)*width*3]) for y in range(height))
    metadata='Capacity (kg); '+ '; '.join(f'{l}={v:g} kg' for l,v in zip(labels,values))
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
            +chunk(b'tEXt',b'Description\0'+metadata.encode('utf-8'))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))


def write_bar_chart(path,labels,values):
    with open(path,'wb') as stream: stream.write(bar_chart(labels,values))
