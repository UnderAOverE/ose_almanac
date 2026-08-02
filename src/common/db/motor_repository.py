#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : motor_repository.py.                                                                #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Base motor repositories - read, write and delete bases for MongoDB collections.     #
# Dependencies  : motor, pymongo, bson, pydantic.                                                     #
# Modifications : 2026-08-02 Shane Reddy - initial.                                                   #
#                                                                                                     #
# Contact       : shanevreddy@gmail.com.                                                              #
#                                                                                                     #
# ----------------------------------------------------------------------------------------------------#
#
#


# ----------------------------------------------------------------------------------------------------#
# Imports.                                                                                            #
# ----------------------------------------------------------------------------------------------------#

import sys

sys.dont_write_bytecode = True

# External imports

from abc import (
    ABC,
    abstractmethod,
)
from typing import Any

import bson
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
)
from pydantic import BaseModel
from pymongo import (
    UpdateMany,
    UpdateOne,
)
from pymongo import errors as pymongo_errors
from pymongo.results import (
    BulkWriteResult,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)

# Internal imports

# None.

# Internal constants

module_version: str = "1.0.0v"

# Raw Mongo documents cross the repository boundary as plain dicts; everything above this layer
# works with validated pydantic models.
type MongoDocument = dict[str, Any]


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class DuplicateKeyError(Exception):

    """
    Raised when an insert violates a unique index, carrying the offending key values.
    """

    def __init__(
            self,
            message: str,
            duplicate_key: MongoDocument | None = None,
    ) -> None:

        """
        Initializes the error with a message and the duplicate key values.

        :param message: human-readable description of the failure.
        :type message: str
        :param duplicate_key: the key values that collided, when the server reports them.
        :type duplicate_key: MongoDocument | None
        :return: None.
        :rtype: None
        """

        self.duplicate_key = duplicate_key
        super().__init__(message)

    # endDef

# endClass


class BaseReadMotorRepository[T: BaseModel](ABC):

    """
    BaseReadMotorRepository class: base repository for read operations on MongoDB collections.
    Subclasses must define the _database_name and _collection_name class attributes.
    """

    _database_name: str
    _collection_name: str

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
            base_model: type[T],
    ) -> None:

        """
        BaseReadMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :param base_model: the pydantic model class representing the documents in the collection.
        :type base_model: type[T]
        :return: None.
        :rtype: None
        :raises NotImplementedError: if the subclass does not define _collection_name or _database_name.
        """

        if not hasattr(self, "_collection_name") or not self._collection_name:
            raise NotImplementedError("Subclasses must define _collection_name")

        # endIf

        if not hasattr(self, "_database_name") or not self._database_name:
            raise NotImplementedError("Subclasses must define _database_name")

        # endIf

        self.db_client: AsyncIOMotorClient = db_client
        self._collection: AsyncIOMotorCollection = db_client[self._database_name][self._collection_name]
        self._base_model = base_model

    # endDef

    def _read_map_to_model(
            self,
            doc: MongoDocument,
    ) -> T:

        """
        Maps a MongoDB document to the model type T.

        :param doc: the MongoDB document to map.
        :type doc: MongoDocument
        :return: an instance of type T.
        :rtype: T
        """

        return self._base_model(**doc)

    # endDef

    async def _execute_find_one(
            self,
            filter_query: MongoDocument,
    ) -> MongoDocument | None:

        """
        Executes a find_one operation on the collection.

        :param filter_query: the filter query to find the document.
        :type filter_query: MongoDocument
        :return: the matching document, or None when nothing matches.
        :rtype: MongoDocument | None
        """

        try:
            return await self._collection.find_one(filter_query)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_find_one for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_find_many(
            self,
            filter_query: MongoDocument,
            sort: list[tuple[str, int]] | None = None,
            limit: int = 0,
    ) -> list[MongoDocument]:

        """
        Executes a find operation on the collection, fully materializing the cursor.

        :param filter_query: the filter query to find the documents.
        :type filter_query: MongoDocument
        :param sort: optional sort specification as (field, direction) pairs.
        :type sort: list[tuple[str, int]] | None
        :param limit: maximum number of documents to return; 0 means no limit.
        :type limit: int
        :return: the matching documents.
        :rtype: list[MongoDocument]
        """

        try:
            cursor = self._collection.find(filter_query)

            if sort:
                cursor = cursor.sort(sort)

            # endIf

            if limit:
                cursor = cursor.limit(limit)

            # endIf

            return await cursor.to_list(length=limit or None)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_find_many for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_count(
            self,
            filter_query: MongoDocument,
    ) -> int:

        """
        Counts the documents matching the filter query.

        :param filter_query: the filter query to count documents for.
        :type filter_query: MongoDocument
        :return: the number of matching documents.
        :rtype: int
        """

        try:
            return await self._collection.count_documents(filter_query)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_count for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_pipeline(
            self,
            pipeline: list[MongoDocument],
            allow_disk_use: bool = False,
    ) -> list[MongoDocument]:

        """
        Executes an aggregation pipeline on the collection.

        :param pipeline: the aggregation pipeline to execute.
        :type pipeline: list[MongoDocument]
        :param allow_disk_use: whether to allow disk use for the aggregation.
        :type allow_disk_use: bool
        :return: a list of documents resulting from the aggregation.
        :rtype: list[MongoDocument]
        """

        try:
            cursor = self._collection.aggregate(pipeline, allowDiskUse=allow_disk_use)
            return await cursor.to_list(length=None)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_pipeline for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

# endClass


class BaseWriteMotorRepository[T: BaseModel](ABC):

    """
    BaseWriteMotorRepository class: base repository for write operations on MongoDB collections.
    Subclasses must define the _database_name and _collection_name class attributes.
    """

    _database_name: str
    _collection_name: str

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
            base_model: type[T],
    ) -> None:

        """
        BaseWriteMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :param base_model: the pydantic model class representing the documents in the collection.
        :type base_model: type[T]
        :return: None.
        :rtype: None
        :raises NotImplementedError: if the subclass does not define _collection_name or _database_name.
        """

        if not hasattr(self, "_collection_name") or not self._collection_name:
            raise NotImplementedError("Subclasses must define _collection_name")

        # endIf

        if not hasattr(self, "_database_name") or not self._database_name:
            raise NotImplementedError("Subclasses must define _database_name")

        # endIf

        self.db_client: AsyncIOMotorClient = db_client
        self._collection: AsyncIOMotorCollection = db_client[self._database_name][self._collection_name]
        self._base_model = base_model

    # endDef

    def _write_map_to_model(
            self,
            doc: MongoDocument,
    ) -> T:

        """
        Maps a MongoDB document to the model type T.

        :param doc: the MongoDB document to map.
        :type doc: MongoDocument
        :return: an instance of type T.
        :rtype: T
        """

        return self._base_model(**doc)

    # endDef

    @staticmethod
    def _write_map_to_document(
            model: T,
    ) -> MongoDocument:

        """
        Maps the model type T to a MongoDB document.

        :param model: the model instance to map.
        :type model: T
        :return: a MongoDB document representation of the model.
        :rtype: MongoDocument
        """

        # Pydantic v2: model_dump instead of dict
        doc = model.model_dump(by_alias=True, exclude_none=True)

        # Ensure _id is ObjectId if present and not None
        if "_id" in doc and doc["_id"] is not None and not isinstance(doc["_id"], bson.ObjectId):
            doc["_id"] = bson.ObjectId(doc["_id"])

        elif "_id" in doc and doc["_id"] is None:  # Remove if id was None and became a null field
            del doc["_id"]

        # endIfElif

        return doc

    # endDef

    async def _execute_insert_one(
            self,
            document: MongoDocument,
    ) -> InsertOneResult:

        """
        Executes an insert_one operation on the collection.

        :param document: the document to insert.
        :type document: MongoDocument
        :return: the result of the insert operation.
        :rtype: InsertOneResult
        :raises DuplicateKeyError: when the insert violates a unique index.
        """

        try:
            return await self._collection.insert_one(document)

        except pymongo_errors.DuplicateKeyError as duplicate_key_error:
            raise DuplicateKeyError(
                message=f"Duplicate key error for document: {duplicate_key_error}",
                duplicate_key=(duplicate_key_error.details or {}).get("keyValue", None),
            ) from duplicate_key_error

        except bson.errors.InvalidDocument:
            raise RuntimeError(f"Invalid document error in _execute_insert_one for {self._collection_name}")

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_insert_one for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_insert_many(
            self,
            documents: list[MongoDocument],
    ) -> InsertManyResult:

        """
        Executes an insert_many operation on the collection.

        :param documents: a list of documents to insert.
        :type documents: list[MongoDocument]
        :return: the result of the insert operation.
        :rtype: InsertManyResult
        """

        if not documents:
            return InsertManyResult(inserted_ids=[], acknowledged=True)

        # endIf

        try:
            return await self._collection.insert_many(documents, ordered=False)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_insert_many for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_update_one(
            self,
            filter_query: MongoDocument,
            update_doc: MongoDocument,
            upsert: bool = False,
    ) -> UpdateResult:

        """
        Executes an update_one operation on the collection.

        :param filter_query: the filter query to find the document to update.
        :type filter_query: MongoDocument
        :param update_doc: the update document containing the changes to apply.
        :type update_doc: MongoDocument
        :param upsert: whether to insert a new document if no document matches the filter.
        :type upsert: bool
        :return: the result of the update operation.
        :rtype: UpdateResult
        """

        try:
            return await self._collection.update_one(filter_query, update_doc, upsert=upsert)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_update_one for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_update_many(
            self,
            filter_query: MongoDocument,
            update_doc: MongoDocument,
            upsert: bool = False,
    ) -> UpdateResult:

        """
        Executes an update_many operation on the collection.

        :param filter_query: the filter query to find the documents to update.
        :type filter_query: MongoDocument
        :param update_doc: the update document containing the changes to apply.
        :type update_doc: MongoDocument
        :param upsert: whether to insert new documents if no documents match the filter.
        :type upsert: bool
        :return: the result of the update operation.
        :rtype: UpdateResult
        """

        try:
            return await self._collection.update_many(filter_query, update_doc, upsert=upsert)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_update_many for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_bulk_updates(
            self,
            update_docs: list[UpdateMany | UpdateOne],
            ordered: bool = True,
    ) -> BulkWriteResult:

        """
        Executes a bulk write operation on the collection for multiple update documents.

        ordered true (default): operations execute one after the other and stop at the first
        error, leaving the remaining operations unattempted - safer when operations depend on
        each other. ordered false: operations may execute in parallel or in arbitrary order and
        the server continues past individual failures - faster for large batches where isolated
        failures are acceptable.

        :param update_docs: a list of update operations (UpdateMany or UpdateOne) to be performed.
        :type update_docs: list[UpdateMany | UpdateOne]
        :param ordered: whether to execute the operations in order.
        :type ordered: bool
        :return: the result of the bulk write operation.
        :rtype: BulkWriteResult
        """

        try:
            return await self._collection.bulk_write(update_docs, ordered=ordered)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_bulk_write_many for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_pipeline(
            self,
            pipeline: list[MongoDocument],
            allow_disk_use: bool = False,
    ) -> list[MongoDocument]:

        """
        Executes an aggregation pipeline on the collection.

        :param pipeline: the aggregation pipeline to execute.
        :type pipeline: list[MongoDocument]
        :param allow_disk_use: whether to allow disk use for the aggregation.
        :type allow_disk_use: bool
        :return: a list of documents resulting from the aggregation.
        :rtype: list[MongoDocument]
        """

        try:
            cursor = self._collection.aggregate(pipeline, allowDiskUse=allow_disk_use)
            return await cursor.to_list(length=None)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_pipeline for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    @abstractmethod
    async def create(
            self,
            entity: T,
    ) -> T:

        """
        Creates a new document in the collection.

        :param entity: the entity to create.
        :type entity: T
        :return: the created entity.
        :rtype: T
        """

        ...

    # endAsyncDef

    @abstractmethod
    async def create_many(
            self,
            entities: list[T],
    ) -> list[T]:

        """
        Creates multiple documents in the collection.

        :param entities: a list of entities to create.
        :type entities: list[T]
        :return: a list of created entities.
        :rtype: list[T]
        """

        ...

    # endAsyncDef

    @abstractmethod
    async def update_one(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> T | None:

        """
        Updates a single document matching the filter query.

        :param filter_query: the filter query to find the document to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert a new document if no document matches the filter.
        :type upsert: bool
        :return: the updated document or None if no document was updated.
        :rtype: T | None
        """

        ...

    # endAsyncDef

    @abstractmethod
    async def update_many(
            self,
            filter_query: MongoDocument,
            update_doc_payload: MongoDocument,
            upsert: bool = False,
    ) -> int:

        """
        Updates multiple documents matching the filter query.

        :param filter_query: the filter query to find the documents to update.
        :type filter_query: MongoDocument
        :param update_doc_payload: the update document containing the changes to apply.
        :type update_doc_payload: MongoDocument
        :param upsert: whether to insert new documents if no documents match the filter.
        :type upsert: bool
        :return: the number of documents updated.
        :rtype: int
        """

        ...

    # endAsyncDef

# endClass


class BaseDeleteMotorRepository[T: BaseModel](ABC):

    """
    BaseDeleteMotorRepository class: base repository for delete operations on MongoDB
    collections. Subclasses must define the _database_name and _collection_name class attributes.
    """

    _database_name: str
    _collection_name: str

    def __init__(
            self,
            db_client: AsyncIOMotorClient,
            base_model: type[T],
    ) -> None:

        """
        BaseDeleteMotorRepository constructor.

        :param db_client: MongoDB client.
        :type db_client: AsyncIOMotorClient
        :param base_model: the pydantic model class representing the documents in the collection.
        :type base_model: type[T]
        :return: None.
        :rtype: None
        :raises NotImplementedError: if the subclass does not define _collection_name or _database_name.
        """

        if not hasattr(self, "_collection_name") or not self._collection_name:
            raise NotImplementedError("Subclasses must define _collection_name")

        # endIf

        if not hasattr(self, "_database_name") or not self._database_name:
            raise NotImplementedError("Subclasses must define _database_name")

        # endIf

        self.db_client: AsyncIOMotorClient = db_client
        self._collection: AsyncIOMotorCollection = db_client[self._database_name][self._collection_name]
        self._base_model = base_model

    # endDef

    async def _execute_delete_one(
            self,
            filter_query: MongoDocument,
    ) -> DeleteResult:

        """
        Executes a delete_one operation on the collection.

        :param filter_query: the filter query to find the document to delete.
        :type filter_query: MongoDocument
        :return: the result of the delete operation.
        :rtype: DeleteResult
        """

        try:
            return await self._collection.delete_one(filter_query)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_delete_one for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    async def _execute_delete_many(
            self,
            filter_query: MongoDocument,
    ) -> DeleteResult:

        """
        Executes a delete_many operation on the collection.

        :param filter_query: the filter query to find the documents to delete.
        :type filter_query: MongoDocument
        :return: the result of the delete operation.
        :rtype: DeleteResult
        """

        try:
            return await self._collection.delete_many(filter_query)

        except Exception as generic_exception:
            raise RuntimeError(f"Error in _execute_delete_many for {self._collection_name}: {generic_exception}")

        # endTryExcept

    # endAsyncDef

    @abstractmethod
    async def delete_one(
            self,
            filter_query: MongoDocument,
    ) -> bool:

        """
        Deletes a single document matching the filter query.

        :param filter_query: the filter query to find the document to delete.
        :type filter_query: MongoDocument
        :return: True if a document was deleted, False otherwise.
        :rtype: bool
        """

        ...

    # endAsyncDef

    @abstractmethod
    async def delete_many(
            self,
            filter_query: MongoDocument,
    ) -> int:

        """
        Deletes multiple documents matching the filter query.

        :param filter_query: the filter query to find the documents to delete.
        :type filter_query: MongoDocument
        :return: the number of documents deleted.
        :rtype: int
        """

        ...

    # endAsyncDef

# endClass


# end_motor_repository.py
