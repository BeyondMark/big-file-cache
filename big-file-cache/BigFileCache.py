# -*- coding: utf-8 -*-
import math
import os
import re
import asyncio
from typing import List

import aiofiles


class CacheFile:
    file_lines: List[str]

    def __init__(self, file_path):
        file_name = os.path.basename(file_path)
        self.file_path = file_path
        self.file_name = file_name
        self.begin_line = int(re.findall(r"[0-9]*_", file_name)[0][:-1])
        self.end_line = int(re.findall(r"_[0-9]*", file_name)[0][1:])

    def read_line(self, index):
        if hasattr(self, "file_lines"):
            return self.file_lines[index]
        with open(self.file_path, "r") as fp:
            self.file_lines = fp.readlines()
            return self.file_lines[index]


class BigFileCache:
    MAX_CACHE_FILE_LINE_COUNT = 10000
    KB = 1024
    MB = KB * 1024
    GB = MB * 1024
    TB = GB * 1024
    SPLIT_FILE_SIZE = 10 * MB

    def __init__(self, file_path, overlay=False):
        self.__file_path = file_path
        self.__cache_files = []
        if overlay:
            self.__delete_cache_files()
        if not self.__check_cache_is_already():
            asyncio.run(self.__create_cache_files())
        self.file_line_count = self.get_file_line_count()

    async def __create_cache_file(self, data_lines: list, begin_len_count):
        lines_len = len(data_lines)
        cache_files_count = int(math.ceil(lines_len / self.MAX_CACHE_FILE_LINE_COUNT))
        for index in range(0, cache_files_count):
            cache_data_begin = index * self.MAX_CACHE_FILE_LINE_COUNT
            cache_data_end = cache_data_begin + self.MAX_CACHE_FILE_LINE_COUNT
            if cache_data_end > lines_len:
                cache_data_end = lines_len
            cache_file_name = "{}\\{}_{}.cache".format(
                os.path.dirname(self.__file_path),
                begin_len_count + cache_data_begin,
                begin_len_count + cache_data_end - 1
            )
            await self.__new_cache_file(cache_file_name, data_lines[cache_data_begin:cache_data_end])
            self.__cache_files.append(CacheFile(cache_file_name))

    @staticmethod
    async def __new_cache_file(file_path: str, cache_data: list):
        async with aiofiles.open(file_path, "w") as fp:
            await fp.writelines(cache_data)

    async def __create_cache_files(self):
        if not self.__file_path:
            return None
        async with aiofiles.open(self.__file_path, "r") as fp:
            file_lines = 1
            while True:
                split_file_data: str = await fp.read(self.SPLIT_FILE_SIZE)
                if not split_file_data:
                    break
                while True:
                    if not split_file_data.endswith("\n"):
                        split_file_data += await fp.read(1)
                    else:
                        break
                split_file_lines = re.findall(r".*\n", split_file_data)
                await self.__create_cache_file(split_file_lines, file_lines)
                file_lines += len(split_file_lines)

    @staticmethod
    def __get_all_cache_file_names(path):
        cache_files_list = []
        for file_name in os.listdir(path):
            if ".cache" in file_name:
                cache_files_list.append(path + "/" + file_name)
        return cache_files_list

    def __delete_cache_files(self):
        path = os.path.dirname(self.__file_path)
        cache_files_list = self.__get_all_cache_file_names(path)
        for cache_file in cache_files_list:
            os.remove(cache_file)

    def __check_cache_is_already(self):
        path = os.path.dirname(self.__file_path)
        cache_files_list = self.__get_all_cache_file_names(path)
        cache_files_size = 0
        for cache_file in cache_files_list:
            cache_files_size += os.path.getsize(cache_file)
        if cache_files_size == os.path.getsize(self.__file_path):
            self.__cache_files = [CacheFile(x) for x in cache_files_list]
            return True
        else:
            self.__delete_cache_files()

    def get_file_line_count(self):
        if hasattr(self, "file_line_count"):
            return self.file_line_count
        max_line_count = 0
        for cache_file in self.__cache_files:
            if max_line_count < cache_file.end_line:
                max_line_count = cache_file.end_line
        return max_line_count

    def read_line(self, index):
        cache_file = self.__find_cache_file_by_index(index)
        if cache_file:
            return cache_file.read_line(index - cache_file.begin_line)

    def read_lines(self, begin, end):
        for index in range(begin, end):
            yield self.read_line(index)

    def __find_cache_file_by_index(self, index) -> CacheFile:
        if index > self.file_line_count:
            raise IndexError("File line count:%d, but input line count is:%d" % (self.file_line_count, index))
        for cache_file in self.__cache_files:
            if cache_file.begin_line <= index <= cache_file.end_line:
                return cache_file

