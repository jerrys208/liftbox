
import logging
import os
import piexif
import json
import shutil

from time import ctime
from datetime import datetime
from os import makedirs, listdir
from os.path import join, basename, pardir, abspath, splitext, exists

from PIL import Image
from PIL.ExifTags import TAGS



""" 照片分類

需求:
    1. 檢驗重複 (根據 exif 精確時間)
    2. 依日期分類 (張數太少自動合併)
    3. 標示模糊
    4. 重新命名 P01706120001.jpg
    5. 影片處理
    6. 將以分類的目錄寫入 exif

流程:
    1. 指定根目錄
    2. 檢視每張照片 (根據副檔名篩選)
    3. 根據 exif 取得日期資訊

"""


#########################################################################
# 操作 EXIF

def read_image_datetime(filename):
    image = Image.open(filename)
    # 使用 pillow 的相容性較佳
    # exif_dict = piexif.load(image.info["exif"])
    # if 'Exif' in exif_dict and 36867 in exif_dict['Exif']:
    #     return exif_dict['Exif'][36867]
    # if '0th' in exif_dict and 306 in exif_dict['0th']:
    #     return exif_dict['0th'][306]
    # logging.error('read exif error: %s', filename)
    # raise RuntimeError('datetime not found in EXIF: %s' % filename)
    exif = image._getexif()
    if exif:
        if 36867 in exif.keys():
            #return exif[36867][0:10].replace(':','')  # 2011:10:08 -> 20111008
            #return exif[36867][0:7].replace(':','')  # 2011:10:08 -> 20111008
            return exif[36867].replace(':', '').replace(' ', '_')
        elif 306 in exif.keys():
            #return exif[306][0:10].replace(':','')  # 2011:10:08 -> 20111008
            #return exif[306][0:7].replace(':','')  # 2011:10:08 -> 20111008
            return exif[306].replace(':', '').replace(' ', '_')

    # check file property
    stat = os.stat(filename)
    if hasattr(stat, 'st_mtime'):
        return datetime.strftime(datetime.fromtimestamp(stat.st_mtime), "%Y%m%d_%H%M%S")
    #st_ctime
    #st_atime
    print("exif err: %s \n%s" % (exif, filename))
    # raise RuntimeError('datetime not found in EXIF: %s' % filename)
    return None

def read_exif(filename):
    logging.info('read_exif(%s)[+]', filename)
    image = Image.open(filename)
    exif_dict = piexif.load(image.info["exif"])
    # DateTimeOriginal = exif_dict['Exif'][36867]
    # UserComment = exif_dict['Exif'][37510]
    # PixelXDimension = exif_dict['Exif'][40962]
    # PixelYDimension = exif_dict['Exif'][40963]
    # logging.info('%s %s %s %s', DateTimeOriginal, UserComment, PixelXDimension, PixelYDimension)
    for ifd in ("0th", "Exif", "GPS", "1st"):
        for tag in exif_dict[ifd]:
            logging.info('%s.%s %s %s', ifd, tag, piexif.TAGS[ifd][tag]["name"], exif_dict[ifd][tag])


def test_exif():
    path = '/media/jerry/D_DAT/_Photo/002_已整理/20100710_大溪老街/DSC_3478.JPG'
    image = Image.open(path)
    # https://stackoverflow.com/questions/17042602/preserve-exif-data-of-image-with-pil-when-resizecreate-thumbnail/33885893#33885893
    # https://github.com/hMatoba/Piexif
    print('exif raw:', image.info['exif'])
    exif_dict = piexif.load(image.info["exif"])
    print('exif dict:')
    for ifd in ("0th", "Exif", "GPS", "1st"):
        for tag in exif_dict[ifd]:
            # print(ifd, piexif.TAGS[ifd][tag]["name"], exif_dict[ifd][tag])
            pass
    # for k, v in exif_dict.items():
    #     print(k, v)
    #exif_bytes = piexif.dump(exif_dict)

    # print( "%s, %s, %s"%(image.format, image.size, hasattr( image, '_getexif' )))
    if hasattr( image, '_getexif' ):
        exifinfo = image._getexif()
        print(exifinfo)
        if exifinfo != None:
            # 36867  DateTimeOriginal
            # 36868  DateTimeDigitized
            # 306      DateTime (修改日期)
            print(exifinfo[36867])
            #for tag, value in exifinfo.items():
            #    decoded = TAGS.get(tag, tag)
            #    print( tag, "|", decoded, "|", value )


class Picture(object):
    def __init__(self, filename):
        self.filename = filename
        self.datetime = read_image_datetime(filename)

    def get_dst_file(self, target):
        # root/year/date/
        ext = splitext(self.filename)[1].lower()
        ext = '.jpg' if ext == '.jpeg' else ext
        return join(target, self.datetime[0:4], self.datetime[0:8], self.datetime + ext)

    def move_to_dst(self, target):
        logging.info('move: %s', self.filename)
        # check datetime
        if self.datetime is None:
            logging.info('cannot get datetime: %s', self.filename)
            return
        filename = self.get_dst_file(target)
        # check parent folder
        folder = abspath(join(filename, pardir))
        if not exists(folder):
            makedirs(folder)
        # check dest file not exists
        path, ext = splitext(filename)
        for i in range(100):
            newfile = ''.join([path, str(i), ext])
            if not exists(newfile):
                logging.info('%s -> %s', self.filename, newfile)
                shutil.move(self.filename, newfile)
                break


class Folder(object):
    def __init__(self, dirname):
        self.dirname = dirname
        self.date = basename(dirname)
        self.count = len(listdir(self.dirname))

    def rename(self, new_name):
        # parent = abspath(join(self.dirname, pardir))
        new_path = self.dirname + '_' + new_name
        logging.info('%s -> %s', self.dirname, new_path)
        shutil.move(self.dirname, new_path)
        self.dirname = new_path

    def __repr__(self):
        return '%s(%d)' % (self.dirname, self.count)


def list_picture(dirs):
    """ 列出所有 image """
    for dir in dirs:
        logging.info('dir[%s]...', dir)
        for dir_name, subdir_list, file_list in os.walk(dir):
            for basename in file_list:
                if basename.lower().endswith(".jpg") or basename.lower().endswith(".jpeg"):
                    yield Picture(join(dir_name, basename))


def list_date_folder(dir):
    for dir_name, subdir_list, file_list in os.walk(dir):
        # logging.info('dir[%s]...', dir_name)
        for name in subdir_list:
            if len(name) == 8:
                yield Folder(join(dir_name, name))


#########################################################################
# 消除重複檔案
import photohash

def search_duplicated(dirs, perceptual=False):
    images = {}
    for image in list_picture(dirs):
        imhash = photohash.average_hash(image)
        if imhash in images:
            logging.warning('duplicated: %s', imhash)
            logging.warning('  f1: %s', images[imhash])
            logging.warning('  f2: %s', image)
        else:
            images[imhash] = image


#########################################################################
# 建立目錄
"""
    2016
    2017
      + 20170123_xxxxx
      + 20170130_xxxxx (>25)

"""
def move_picture(dirs, target):
    for picture in list_picture(dirs):
        picture.move_to_dst(target)


#########################################################################
# 重新命名檔案

def rename_image(dirs):
    """
    1. 名稱: YYYYMMDDHHMMSS.jpg 重複時秒數加 1
    """
    names = {}
    for image in list_picture(dirs):
        datetime = read_image_datetime(image)
        if datetime is None:
            continue
        datetime = datetime.replace(':', '').replace(' ', '_')
        if datetime in names:
            logging.warning('duplicated: %s', datetime)
            logging.warning('  f1: %s', names[datetime])
            logging.warning('  f2: %s', image)
        else:
            names[datetime] = image
        _rename_with_check(image, datetime)


def _rename_with_check(filename, new_name):
    # logging.info('rename: %s -> %s', filename, new_name)
    name, ext = splitext(basename(filename))
    #if name == new_name:
    #    return
    folder = abspath(join(filename, pardir))
    ext = ext.lower()
    ext = '.jpg' if ext == '.jpeg' else ext
    for i in range(100):
        newfile = join(folder, ''.join([new_name, str(i), ext]))
        if not exists(newfile):
            logging.info('%s -> %s', filename, newfile)
            shutil.move(filename, newfile)
            break

#########################################################################
# 紀錄已標住的目錄 (date: note)

def restore_date_note(dir):
    note = load_date_note()
    used = set()
    for f in list_date_folder(dir):
        if f.date in note:
            used.add(f.date)
            new_name = note[f.date]
            f.rename(new_name)
    # list un-used
    for date in (note.keys() - used):
        print(date, note[date])

def load_date_note():
    with open('./note.txt', 'r') as src:
        res = json.load(src)
    print(res)
    return res


def dump_date_note(root_dir):
    beg = len(root_dir)+1
    res = {}
    for dir_name, subdir_list, file_list in os.walk(root_dir):
        if dir_name == root_dir:
            continue
        date, note = dir_name[beg:].split('_')
        res[date] = note
    with open('./note.txt', 'w') as out:
        json.dump(res, out)


#########################################################################
# Main

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)-15s %(levelname)s %(message)s', level=logging.INFO)
    logging.info('start')
    # search_duplicated(['/media/jerry/D_DAT/_Photo/002_已整理/20090308_宸瑀生活照', '/media/jerry/D_DAT/_Photo/宸瑀'])
    # rename_image(['/media/jerry/D_DAT/_Photo/000_待分日/wanyun'])
    # move_picture(['/media/jerry/D_DAT/_Photo/000_整理/arc'], '/media/jerry/D_DAT/_Photo/001_照片')
    # print(read_image_datetime('/media/jerry/D_DAT/_Photo/000_整理/無法判定/00000752.jpg'))

    # restore_date_note('/media/jerry/D_DAT/_Photo/001_照片')

    # read_exif('/media/jerry/D_DAT/_Photo/002_已整理/20130106_柯達阿公慶生/DSC_4603.JPG')
    # read_exif('/media/jerry/D_DAT/_Photo/002_已整理/20130106_柯達阿公慶生/IMAG0343.jpg')
    # dump_date_note('/media/jerry/D_DAT/_Photo/002_已整理')
    # load_date_note()