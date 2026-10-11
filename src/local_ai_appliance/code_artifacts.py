"""Bounded artifact inspection without invoking host code or image applications."""
import struct
import zlib

from .folders import AccessDenied


def png_pixels(data):
    if not isinstance(data,bytes) or not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data)>1024*1024:
        raise AccessDenied('Invalid bounded PNG')
    offset=8; compressed=bytearray(); header=None; ended=False; chunks=0
    while offset<len(data):
        if len(data)-offset<12 or chunks>64: raise AccessDenied('Invalid PNG chunk inventory')
        size=struct.unpack_from('>I',data,offset)[0]; kind=data[offset+4:offset+8]
        end=offset+12+size
        if end>len(data): raise AccessDenied('Truncated PNG')
        payload=data[offset+8:end-4]
        if zlib.crc32(kind+payload)&0xffffffff != struct.unpack_from('>I',data,end-4)[0]:
            raise AccessDenied('PNG checksum mismatch')
        if header is None and kind!=b'IHDR': raise AccessDenied('PNG missing leading header')
        if kind==b'IHDR':
            if header is not None or size!=13: raise AccessDenied('Invalid PNG header')
            header=struct.unpack('>IIBBBBB',payload)
        elif kind==b'IDAT': compressed.extend(payload)
        elif kind==b'IEND':
            if size or end!=len(data): raise AccessDenied('Invalid PNG end')
            ended=True; break
        elif kind not in {b'tEXt'}: raise AccessDenied('Unsupported PNG chunk')
        offset=end; chunks+=1
    if not ended or header is None: raise AccessDenied('Incomplete PNG')
    width,height,depth,color,compression,filtering,interlace=header
    if not 1<=width<=1024 or not 1<=height<=768 or (depth,color,compression,filtering,interlace)!=(8,2,0,0,0):
        raise AccessDenied('Only bounded noninterlaced RGB charts are supported')
    expected=height*(width*3+1)
    inflater=zlib.decompressobj()
    try: raw=inflater.decompress(bytes(compressed),expected+1)
    except zlib.error: raise AccessDenied('Invalid PNG compression') from None
    if len(raw)!=expected or not inflater.eof or inflater.unconsumed_tail or inflater.unused_data:
        raise AccessDenied('Invalid or overexpanded PNG pixels')
    stride=width*3+1
    if any(raw[row*stride]!=0 for row in range(height)):
        raise AccessDenied('Only unfiltered charts from the offline helper are supported')
    return width,height,raw


def png_preview(data):
    width,height,raw=png_pixels(data); stride=width*3+1
    lines=[f'PNG chart: {width} x {height} pixels (sampled preview)']
    for y in range(0,height,max(1,height//18)):
        row=''
        for x in range(0,width,max(1,width//64)):
            color=raw[y*stride+1+x*3:y*stride+4+x*3]
            row+=' ' if min(color)>230 else '#'
        lines.append(row)
    return '\n'.join(lines)


def validate_artifact(path,data):
    if path.endswith('.png'): png_pixels(data)
    else:
        if len(data)>32*1024: raise AccessDenied('Text artifact exceeds the inspectable export limit')
        try: data.decode('utf-8')
        except UnicodeError: raise AccessDenied('Text artifact is not UTF-8') from None
