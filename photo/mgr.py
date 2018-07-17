
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

class ImageTool(object):

    @classmethod
    def list_files(cls, dirs, exts):
        """ 列出所有 image ('.jpg', '.jpeg') """
        for dir in dirs:
            logging.info('dir[%s]...', dir)
            for dir_name, subdir_list, file_list in os.walk(dir):
                for basename in file_list:
                    for ext in exts:
                        if basename.lower().endswith(ext):
                            yield join(dir_name, basename)
                            break

    @classmethod
    def read_datetime(cls, filename):
        """ 讀取指定檔案的日期資訊 """
        logging.debug('read_image_datetime(%s)[+]', filename)
        image = Image.open(filename)
        # 使用 pillow 的相容性較 (piexif) 佳
        # exif_dict = piexif.load(image.info["exif"])
        # if 'Exif' in exif_dict and 36867 in exif_dict['Exif']:
        #     return exif_dict['Exif'][36867]
        # if '0th' in exif_dict and 306 in exif_dict['0th']:
        #     return exif_dict['0th'][306]
        # logging.error('read exif error: %s', filename)
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

        logging.error('cannot read image datetime for file: %s', filename)
        # raise RuntimeError('datetime not found in EXIF: %s' % filename)
        return None

    @classmethod
    def read_exif(cls, filename):
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



class Photo(object):
    """ 代表照片 """

    def __init__(self, filename):
        self.filename = filename
        self.datetime = ImageTool.read_datetime(filename)

    def get_dst_file(self, root_dir):
        """ 取得 destination 檔案路徑
            => root_dir/yyyy/yyyymmdd/yyyymmdd_hhmmssi.jpg
        """
        ext = splitext(self.filename)[1].lower()
        ext = '.jpg' if ext == '.jpeg' else ext
        return join(root_dir, self.datetime[0:4], self.datetime[0:8], self.datetime + ext)

    def move_to_dst(self, root_dir):
        logging.info('move: %s', self.filename)
        # check datetime
        if self.datetime is None:
            logging.warning('cannot move file: datetime(%s) is None', self.filename)
            return
        filename = self.get_dst_file(root_dir)
        # check parent folder
        folder = abspath(join(filename, pardir))
        if not exists(folder):
            makedirs(folder)
        # check dest file not exists
        # 名稱: YYYYMMDDHHMMSS.jpg 重複時秒數加 1 ??
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




class DateNote(object):
    """ 代表已標住的目錄 (date: note), e.g. 20111001_陽明員工旅遊紙箱王 """

    @classmethod
    def dump_date_note(cls, root_dir, out_file='note.txt'):
        res = {}
        for dir_name, subdir_list, file_list in os.walk(root_dir):
            for subdir in subdir_list:
                if len(subdir) > 9 and subdir[8] == '_':
                    print(subdir)
                    date = subdir[:8]
                    note = subdir[9:]
                    res[date] = note
        with open(out_file, 'w', encoding='utf8') as out:
            keys = sorted(res.keys())
            for key in keys:
                out.write('{}:{}\n'.format(key, res[key]))

    @classmethod
    def load_date_note(cls, filename='note.txt'):
        res = {}
        with open(filename, 'r', encoding='utf8') as src:
            for line in src:
                key, val = line.split(':')
                res[key] = val.rstrip('\n')
        logging.info('date_note: %s', res)
        return res

    @classmethod
    def list_date_folder(cls, dir):
        for dir_name, subdir_list, file_list in os.walk(dir):
            for name in subdir_list:
                if len(name) == 8:
                    yield Folder(join(dir_name, name))

    @classmethod
    def apply_date_note(cls, dir):
        note = cls.load_date_note()
        used = set()
        for f in list_date_folder(dir):
            if f.date in note:
                used.add(f.date)
                new_name = note[f.date]
                f.rename(new_name)
        # list un-used
        for date in (note.keys() - used):
            print(date, note[date])







#########################################################################
# Main

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)-15s %(levelname)s %(message)s', level=logging.INFO)
    logging.info('start')

    # 管理 date note
    # DateNote.dump_date_note('/home/jerry/_media/_photo/001_照片/')
    # dn = DateNote.load_date_note()

    # restore_date_note('/media/jerry/D_DAT/_Photo/001_照片')

    # search_duplicated(['/media/jerry/D_DAT/_Photo/002_已整理/20090308_宸瑀生活照', '/media/jerry/D_DAT/_Photo/宸瑀'])
    # rename_image(['/media/jerry/D_DAT/_Photo/000_待分日/wanyun'])
    # move_picture(['/media/jerry/D_DAT/_Photo/000_整理/arc'], '/media/jerry/D_DAT/_Photo/001_照片')
    # print(read_image_datetime('/media/jerry/D_DAT/_Photo/000_整理/無法判定/00000752.jpg'))


