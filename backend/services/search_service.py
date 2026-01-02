from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from pymilvus import connections, Collection, utility
from langchain_chroma import Chroma
from services.embedding_service import EmbeddingService
from utils.config import VectorDBProvider, MILVUS_CONFIG, CHROMA_CONFIG
import os
import json

logger = logging.getLogger(__name__)

class SearchService:
    """
    搜索服务类，负责向量数据库的连接和向量搜索功能
    提供集合列表查询、向量相似度搜索和搜索结果保存等功能
    """
    def __init__(self):
        """
        初始化搜索服务
        创建嵌入服务实例，设置Milvus连接URI，初始化搜索结果保存目录
        """
        self.embedding_service = EmbeddingService()
        self.milvus_uri = MILVUS_CONFIG["uri"]
        self.search_results_dir = "04-search-results"
        os.makedirs(self.search_results_dir, exist_ok=True)

    def get_providers(self) -> List[Dict[str, str]]:
        """
        获取支持的向量数据库列表
        
        Returns:
            List[Dict[str, str]]: 支持的向量数据库提供商列表
        """
        return [
            {"id": VectorDBProvider.MILVUS.value, "name": "Milvus"},
            {"id": VectorDBProvider.CHROMA.value, "name": "Chroma"}
        ]

    def list_collections(self, provider: str = VectorDBProvider.MILVUS.value) -> List[Dict[str, Any]]:
        """
        获取指定向量数据库中的所有集合
        
        Args:
            provider (str): 向量数据库提供商，默认为Milvus
            
        Returns:
            List[Dict[str, Any]]: 集合信息列表，包含id、名称和实体数量
            
        Raises:
            Exception: 连接或查询集合时发生错误
        """
        if provider == VectorDBProvider.MILVUS:
            try:
                connections.connect(
                    alias="default",
                    uri=self.milvus_uri
                )
                
                collections = []
                collection_names = utility.list_collections()
                
                for name in collection_names:
                    try:
                        collection = Collection(name)
                        collections.append({
                            "id": name,
                            "name": name,
                            "count": collection.num_entities
                        })
                    except Exception as e:
                        logger.error(f"Error getting info for collection {name}: {str(e)}")
                
                return collections
                
            except Exception as e:
                logger.error(f"Error listing collections: {str(e)}")
                raise
            finally:
                connections.disconnect("default")
        elif provider == VectorDBProvider.CHROMA:
            try:
                # 获取Chroma目录下的所有子目录作为集合名称
                chroma_dir = CHROMA_CONFIG["persist_directory"]
                if not os.path.exists(chroma_dir):
                    return []
                collections = []
                for item in os.listdir(chroma_dir):
                    item_path = os.path.join(chroma_dir, item)
                    if os.path.isdir(item_path):
                        try:
                            chroma_db = Chroma(
                                collection_name=item,
                                persist_directory=CHROMA_CONFIG["persist_directory"]
                            )
                            collections.append({
                                "id": item,
                                "name": item,
                                "count": chroma_db._collection.count()
                            })
                        except Exception as e:
                            logger.error(f"Error getting info for collection {item}: {str(e)}")
                return collections
            except Exception as e:
                logger.error(f"Error listing Chroma collections: {str(e)}")
                raise
        else:
            raise ValueError(f"Unsupported vector database provider: {provider}")

    def save_search_results(self, query: str, collection_id: str, results: List[Dict[str, Any]]) -> str:
        """
        保存搜索结果到JSON文件
        
        Args:
            query (str): 搜索查询文本
            collection_id (str): 集合ID
            results (List[Dict[str, Any]]): 搜索结果列表
            
        Returns:
            str: 保存文件的路径
            
        Raises:
            Exception: 保存文件时发生错误
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            # 使用集合ID的基础名称（去掉路径相关字符）
            collection_base = os.path.basename(collection_id)
            filename = f"search_{collection_base}_{timestamp}.json"
            filepath = os.path.join(self.search_results_dir, filename)
            
            search_data = {
                "query": query,
                "collection_id": collection_id,
                "timestamp": datetime.now().isoformat(),
                "results": results
            }
            
            logger.info(f"Saving search results to: {filepath}")
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Successfully saved search results to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving search results: {str(e)}")
            raise

    async def search(self, 
                    query: str, 
                    collection_id: str, 
                    top_k: int = 3, 
                    threshold: float = 0.7,
                    word_count_threshold: int = 20,
                    save_results: bool = False, 
                    provider: str = VectorDBProvider.MILVUS.value) -> Dict[str, Any]:
        """
        执行向量搜索
        
        Args:
            query (str): 搜索查询文本
            collection_id (str): 要搜索的集合ID
            top_k (int): 返回的最大结果数量，默认为3
            threshold (float): 相似度阈值，低于此值的结果将被过滤，默认为0.7
            word_count_threshold (int): 文本字数阈值，低于此值的结果将被过滤，默认为20
            save_results (bool): 是否保存搜索结果，默认为False
            provider (str): 向量数据库提供商，默认为Milvus
            
        Returns:
            Dict[str, Any]: 包含搜索结果的字典，如果保存结果则包含保存路径
            
        Raises:
            Exception: 搜索过程中发生错误
        """
        try:
            # 添加参数日志
            logger.info(f"Search parameters:")
            logger.info(f"- Query: {query}")
            logger.info(f"- Collection ID: {collection_id}")
            logger.info(f"- Top K: {top_k}")
            logger.info(f"- Threshold: {threshold}")
            logger.info(f"- Word Count Threshold: {word_count_threshold}")
            logger.info(f"- Save Results: {save_results} (type: {type(save_results)})")
            logger.info(f"- Provider: {provider}")

            logger.info(f"Starting search with parameters - Collection: {collection_id}, Query: {query}, Top K: {top_k}")
            
            # 根据不同的数据库执行搜索
            if provider == VectorDBProvider.MILVUS:
                processed_results = await self._search_milvus(
                    query=query,
                    collection_id=collection_id,
                    top_k=top_k,
                    threshold=threshold,
                    word_count_threshold=word_count_threshold
                )
            elif provider == VectorDBProvider.CHROMA:
                processed_results = await self._search_chroma(
                    query=query,
                    collection_id=collection_id,
                    top_k=top_k,
                    threshold=threshold,
                    word_count_threshold=word_count_threshold
                )
            else:
                raise ValueError(f"Unsupported vector database provider: {provider}")

            response_data = {"results": processed_results}
            
            # 添加详细的保存逻辑日志
            logger.info(f"Preparing to handle save_results (flag: {save_results})")
            if save_results:
                logger.info("Save results is True, attempting to save...")
                if processed_results:
                    try:
                        filepath = self.save_search_results(query, collection_id, processed_results)
                        logger.info(f"Successfully saved results to: {filepath}")
                        response_data["saved_filepath"] = filepath
                    except Exception as e:
                        logger.error(f"Error saving results: {str(e)}")
                        response_data["save_error"] = str(e)
                        raise  # 添加这行来查看完整的错误堆栈
                else:
                    logger.info("No results to save")
            else:
                logger.info("Save results is False, skipping save")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            raise
            
    async def _search_milvus(self, 
                           query: str, 
                           collection_id: str, 
                           top_k: int = 3, 
                           threshold: float = 0.7,
                           word_count_threshold: int = 20) -> List[Dict[str, Any]]:
        """
        在Milvus中执行向量搜索
        
        Args:
            query (str): 搜索查询文本
            collection_id (str): 要搜索的集合ID
            top_k (int): 返回的最大结果数量，默认为3
            threshold (float): 相似度阈值，低于此值的结果将被过滤，默认为0.7
            word_count_threshold (int): 文本字数阈值，低于此值的结果将被过滤，默认为20
            
        Returns:
            List[Dict[str, Any]]: 处理后的搜索结果列表
        """
        try:
            # 连接到 Milvus
            logger.info(f"Connecting to Milvus at {self.milvus_uri}")
            connections.connect(
                alias="default",
                uri=self.milvus_uri
            )
            
            # 获取collection
            logger.info(f"Loading collection: {collection_id}")
            collection = Collection(collection_id)
            collection.load()
            
            # 记录collection的基本信息
            logger.info(f"Collection info - Entities: {collection.num_entities}")
            
            # 从collection中读取embedding配置
            logger.info("Querying sample entity for embedding configuration")
            sample_entity = collection.query(
                expr="id >= 0", 
                output_fields=["embedding_provider", "embedding_model"],
                limit=1
            )
            if not sample_entity:
                logger.error(f"Collection {collection_id} is empty")
                raise ValueError(f"Collection {collection_id} is empty")
            
            logger.info(f"Sample entity configuration: {sample_entity[0]}")
            
            # 使用collection中存储的配置创建查询向量
            logger.info("Creating query embedding")
            query_embedding = self.embedding_service.create_single_embedding(
                query,
                provider=sample_entity[0]["embedding_provider"],
                model=sample_entity[0]["embedding_model"]
            )
            logger.info(f"Query embedding created with dimension: {len(query_embedding)}")
            
            # 执行搜索
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10}
            }
            logger.info(f"Executing search with params: {search_params}")
            logger.info(f"Word count threshold filter: word_count >= {word_count_threshold}")
            
            results = collection.search(
                data=[query_embedding],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=f"word_count >= {word_count_threshold}",
                output_fields=[
                    "content",
                    "document_name",
                    "chunk_id",
                    "total_chunks",
                    "word_count",
                    "page_number",
                    "page_range",
                    "embedding_provider",
                    "embedding_model",
                    "embedding_timestamp"
                ]
            )
            
            # 处理结果
            processed_results = []
            logger.info(f"Raw search results count: {len(results[0])}")
            
            for hits in results:
                for hit in hits:
                    logger.info(f"Processing hit - Score: {hit.score}, Word Count: {hit.entity.get('word_count')}")
                    if hit.score >= threshold:
                        processed_results.append({
                            "text": hit.entity.content,
                            "score": float(hit.score),
                            "metadata": {
                                "source": hit.entity.document_name,
                                "page": hit.entity.page_number,
                                "chunk": hit.entity.chunk_id,
                                "total_chunks": hit.entity.total_chunks,
                                "page_range": hit.entity.page_range,
                                "embedding_provider": hit.entity.embedding_provider,
                                "embedding_model": hit.entity.embedding_model,
                                "embedding_timestamp": hit.entity.embedding_timestamp
                            }
                        })
            
            return processed_results
        finally:
            connections.disconnect("default")
            
    async def _search_chroma(self, 
                           query: str, 
                           collection_id: str, 
                           top_k: int = 3, 
                           threshold: float = 0.7,
                           word_count_threshold: int = 20) -> List[Dict[str, Any]]:
        """
        在Chroma中执行向量搜索
        
        Args:
            query (str): 搜索查询文本
            collection_id (str): 要搜索的集合ID
            top_k (int): 返回的最大结果数量，默认为3
            threshold (float): 相似度阈值，低于此值的结果将被过滤，默认为0.7
            word_count_threshold (int): 文本字数阈值，低于此值的结果将被过滤，默认为20
            
        Returns:
            List[Dict[str, Any]]: 处理后的搜索结果列表
        """
        try:
            # 获取Chroma集合
            logger.info(f"Loading Chroma collection: {collection_id}")
            chroma_db = Chroma(
                collection_name=collection_id,
                persist_directory=CHROMA_CONFIG["persist_directory"]
            )
            
            # 获取集合中的第一个文档来确定embedding配置
            logger.info("Getting first document to determine embedding configuration")
            first_doc = chroma_db._collection.peek(limit=1)
            if not first_doc:
                logger.error(f"Collection {collection_id} is empty")
                raise ValueError(f"Collection {collection_id} is empty")
            
            # 从元数据中获取embedding配置
            logger.info(f"Sample document metadata: {first_doc['metadatas'][0]}")
            embedding_provider = first_doc['metadatas'][0].get('embedding_provider')
            embedding_model = first_doc['metadatas'][0].get('embedding_model')
            
            if not embedding_provider or not embedding_model:
                logger.error("Missing embedding configuration in metadata")
                raise ValueError("Missing embedding configuration in metadata")
            
            # 使用collection中存储的配置创建查询向量
            logger.info("Creating query embedding")
            query_embedding = self.embedding_service.create_single_embedding(
                query,
                provider=embedding_provider,
                model=embedding_model
            )
            logger.info(f"Query embedding created with dimension: {len(query_embedding)}")
            
            # 执行搜索
            logger.info(f"Executing Chroma search with top_k: {top_k}")
            results = chroma_db.similarity_search_with_score_by_vector(
                embedding=query_embedding,
                k=top_k,
                filter={"word_count": {"$gte": word_count_threshold}}
            )
            
            # 处理结果
            processed_results = []
            logger.info(f"Raw search results count: {len(results)}")
            
            for doc, score in results:
                # Chroma返回的是余弦相似度，值越小表示越相似
                # 我们需要将其转换为与Milvus一致的相似度表示（值越大越相似）
                similarity_score = 1.0 - score
                logger.info(f"Processing hit - Score: {similarity_score}, Word Count: {doc.metadata.get('word_count')}")
                
                if similarity_score >= threshold:
                    processed_results.append({
                        "text": doc.page_content,
                        "score": float(similarity_score),
                        "metadata": {
                            "source": doc.metadata.get('filename', 'unknown'),
                            "page": doc.metadata.get('page_number', 'unknown'),
                            "chunk": doc.metadata.get('chunk_id', 'unknown'),
                            "total_chunks": doc.metadata.get('total_chunks', 'unknown'),
                            "page_range": doc.metadata.get('page_range', 'unknown'),
                            "embedding_provider": embedding_provider,
                            "embedding_model": embedding_model,
                            "embedding_timestamp": doc.metadata.get('embedding_timestamp', 'unknown')
                        }
                    })
            
            return processed_results
        except Exception as e:
            logger.error(f"Error searching Chroma: {str(e)}")
            raise