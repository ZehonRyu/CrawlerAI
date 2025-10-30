import asyncio
import sys
from typing import Any, Dict, List, Union

import aiomysql
from tools import utils


class AsyncMysqlDB:
    def __init__(self, pool: aiomysql.Pool):
        self.__pool = pool

    async def query(self, sql: str, *args) -> List[Dict[str, Any]]:
        """
        执行SELECT查询
        Args:
            sql: SELECT SQL语句
            *args: SQL参数
        Returns:
            查询结果列表
        """
        async with self.__pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, args)
                results = await cursor.fetchall()
                return results or []

    async def get_first(self, sql: str, *args) -> Union[Dict[str, Any], None]:
        """
        执行SELECT查询并返回第一条结果
        Args:
            sql: SELECT SQL语句
            *args: SQL参数
        Returns:
            第一条查询结果或None
        """
        async with self.__pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, args)
                result = await cursor.fetchone()
                return result

    async def item_to_table(self, table_name: str, item: Dict[str, Any]) -> int:
        """
        插入数据到表中
        Args:
            table_name: 表名
            item: 要插入的数据字典
        Returns:
            插入数据的ID
        """
        if not item:
            return 0

        async with self.__pool.acquire() as conn:
            async with conn.cursor() as cursor:
                keys = item.keys()
                values = tuple(item.values())
                fields = ",".join([f"`{key}`" for key in keys])
                placeholders = ",".join(["%s"] * len(keys))
                sql = f"INSERT INTO `{table_name}` ({fields}) VALUES ({placeholders})"
                await cursor.execute(sql, values)
                await conn.commit()
                return cursor.lastrowid

    async def update_table(
        self, table_name: str, item: Dict[str, Any], query: str
    ) -> int:
        """
        更新表中的数据
        Args:
            table_name: 表名
            item: 要更新的数据字典
            query: 更新条件
        Returns:
            受影响的行数
        """
        if not item:
            return 0

        async with self.__pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 构建SET子句
                set_fields = ",".join([f"`{key}`=%s" for key in item.keys()])
                values = list(item.values())

                # 解析WHERE条件
                where_clause = ""
                if query:
                    where_parts = []
                    for condition in query.split("AND"):
                        condition = condition.strip()
                        if "=" in condition:
                            key, _ = condition.split("=", 1)
                            where_parts.append(f"{key}=%s")
                    where_clause = " AND ".join(where_parts)

                    # 为WHERE条件添加值（这里简化处理，实际应用中需要正确解析查询条件）
                    # 注意：当前实现假设查询条件值与item中的值对应

                sql = f"UPDATE `{table_name}` SET {set_fields}"
                if where_clause:
                    sql += f" WHERE {where_clause}"

                await cursor.execute(sql, values)
                await conn.commit()
                return cursor.rowcount

    async def execute(self, sql: str, *args) -> int:
        """
        执行任意SQL语句
        Args:
            sql: SQL语句
            *args: SQL参数
        Returns:
            受影响的行数
        """
        async with self.__pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, args)
                await conn.commit()
                return cursor.rowcount

    async def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取表结构信息
        Args:
            table_name: 表名
        Returns:
            表结构信息
        """
        sql = "SELECT COLUMN_NAME,DATA_TYPE,COLUMN_COMMENT FROM information_schema.COLUMNS WHERE table_name=%s and table_schema=%s"
        db_name = self.__pool._conn_kwargs.get("db")
        return await self.query(sql, table_name, db_name)

    async def get_all_tables(self) -> List[str]:
        """
        获取数据库中所有表名
        Returns:
            表名列表
        """
        sql = "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s"
        db_name = self.__pool._conn_kwargs.get("db")
        results = await self.query(sql, db_name)
        return [item["TABLE_NAME"] for item in results]
