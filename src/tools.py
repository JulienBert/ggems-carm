from os.path import splitext, join, dirname
from numpy import fromfile, zeros
from numba import jit
import sys

@jit(nopython=True)
def core_array2image(Image, aData, nx, ny):
    ind = 0
    for y in range(ny):
        for x in range(nx):
            # HU -1000 to 3000
            val = aData[y, x]
            
            Image[ind]   = val  # r
            Image[ind+1] = val  # g
            Image[ind+2] = val  # b
            Image[ind+3] = 1

            ind += 4
    return Image

def array2image(aData):
    ny, nx = aData.shape

    image = zeros(4*nx*ny, 'float32')

    # Normalize 01
    aData = aData.astype('float32')
    minVal = aData.min()
    aData -= minVal
    maxVal = aData.max()
    aData /= maxVal

    return core_array2image(image, aData, nx, ny).tolist()

# open MHD file V1.2
def importMHD(pathfilename):
    print("MHD", pathfilename)

    name, ext = splitext(pathfilename)

    if ext != '.mhd':
        print('File must be MHD file (.mhd)!')
        sys.exit()

    
    print(name, ext)

    lines = open(pathfilename, 'r').readlines()

    flagSpacing = False
    flagOffset = False
    flagDimSize = False
    flagNDims = False
    flagType = False
    flagData = False

    for line in lines:

        if line.find('ObjectType =') != -1:
            if line.split()[-1] != 'Image':
                print('[ERROR] MHD file must be an image!')
                sys.exit()

        if line.find('NDims =') != -1:
            ndim = int(line.split()[-1])
            flagNDims = True

            if ndim not in (1, 2, 3):
                print('[ERROR] MHD file must be an image of 1, 2 or 3 dimensions!')
                sys.exit()

        if line.find('BinaryData =') != -1:
            if line.split()[-1] != 'True':
                print('[ERROR] MHD file must be in raw data!')
                sys.exit()

        if line.find('BinaryDataByteOrderMSB =') != -1:
            if line.split()[-1] != 'False':
                print('[ERROR] MHD file must be in MSB byte order!')
                sys.exit()

        if line.find('CompressedData =') != -1:
            if line.split()[-1] != 'False':
                print('[ERROR] MHD file must be not compressed!')
                sys.exit()

        if line.find('TransformMatrix =') != -1:
            pass

        if line.find('Offset =') != -1:
            if ndim == 1:
                ox = line.split()[-1:]
                ox = float(ox)
            elif ndim == 2:
                ox, oy = line.split()[-2:]
                ox, oy = float(ox), float(oy)
            elif ndim == 3:
                ox, oy, oz = line.split()[-3:]
                ox, oy, oz = float(ox), float(oy), float(oz)
            
            flagOffset = True

        if line.find('CenterOfRotation =') != -1:
            pass

        if line.find('ElementSpacing =') != -1:

            if ndim == 1:
                resx = line.split()[-1:]
                resx = float(resx)
            elif ndim == 2:
                resx, resy = line.split()[-2:]
                resx, resy = float(resx), float(resy)
            elif ndim == 3:
                resx, resy, resz = line.split()[-3:]
                resx, resy, resz = float(resx), float(resy), float(resz)

            flagSpacing = True

        if line.find('DimSize =') != -1:
            if ndim == 1:
                nx = line.split()[-1:]
                nx = int(nx)
            elif ndim == 2:
                nx, ny = line.split()[-2:]
                nx, ny = int(nx), int(ny)
            elif ndim == 3:
                nx, ny, nz = line.split()[-3:]
                nx, ny, nz = int(nx), int(ny), int(nz)

            flagDimSize = True

        if line.find('AnatomicalOrientation =') != -1:
            pass

        if line.find('ElementType =') != -1:
            datatype = line.split()[-1]
            flagType = True

        if line.find('ElementDataFile =') != -1:
            filename = line.split()[-1]
            flagData = True

    # Check
    if flagData is False:
        print('[ERROR] ElementDataFile tag missing!')
        sys.exit()
    if flagType is False:
        print('[ERROR] ElementType tag missing!')
        sys.exit()
    if flagDimSize is False:
        print('[ERROR] DimSize tag missing!')
        sys.exit()
    if flagNDims is False:
        print('[ERROR] NDims tag missing!')
        sys.exit()
    if flagOffset is False:
        print('[ERROR] Offset tag missing!')
        sys.exit()
    if flagSpacing is False:
        print('[ERROR] ElementSpacing tag missing!')
        sys.exit()

    path = dirname(pathfilename)
    if path != "":
        filename = join(path, filename)

    if datatype == 'MET_FLOAT': datatype = 'float32'
    elif datatype == 'MET_INT': datatype = 'int32'
    elif datatype == 'MET_SHORT': datatype = 'int16'
    elif datatype == 'MET_UCHAR': datatype = 'uint8'
    else:
        print('[ERROR] MHD data type unknown:', datatype)
        sys.exit()

    arrayRaw = fromfile(filename, datatype)
    arrayRaw = arrayRaw.reshape((nz, ny, nx))
    dictHeader = {
        'ndims': ndim,
        'shape': [nx, ny, nz],
        'offset': [ox, oy, oz],
        'spacing': [resx, resy, resz]
    }

    return arrayRaw, dictHeader