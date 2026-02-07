"""
Pipeline RAG avec logging complet des métriques.
"""
import time
import uuid
from typing import List, Dict
from app.core.database import AsyncSessionLocal
from app.services.embeddings import vectorize_query
from app.services.llm import generate_response
from sqlalchemy import text
import logging
import json

logger = logging.getLogger(__name__)

# Pricing Voyage AI
VOYAGE_PRICE_PER_MILLION = 0.13


async def search_context(embedding: List[float], top_k: int = 6) -> List[Dict]:
    """
    Recherche vector similarity dans experiences + projects + formations.
    
    Returns:
        Liste de dicts avec {type, id, title, description, score}
    """
    async with AsyncSessionLocal() as db:
        query_sql = text("""
            (
                SELECT 
                    'experience' as type,
                    experiences.id,
                    role as title,
                    TO_CHAR(experiences.start_date, 'YYYY-MM-DD') || ' à ' || TO_CHAR(experiences.end_date,   'YYYY-MM-DD') || ' description : ' || context || ' ' || objective || ' ' || problem || ' ' || solution || ' ' || results || ' ' || impact || ' ' || description   as description,
                    1 - (experiences.embedding <=> CAST(:embedding AS vector)) as score
                FROM experiences, projects
                WHERE experiences.embedding IS NOT NULL 
                AND experiences.id = projects.experience_id
            )
            UNION ALL
            (
                SELECT 
                    'formation' as type,
                    id,
                    degree as title,
                    TO_CHAR(start_date, 'YYYY-MM-DD') || ' à ' || TO_CHAR(end_date,   'YYYY-MM-DD') || ' description ' || description,
                    1 - (embedding <=> CAST(:embedding AS vector)) as score
                FROM formations
                WHERE embedding IS NOT NULL
            )
            ORDER BY score DESC
            LIMIT :top_k
        """)
        
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        
        result = await db.execute(
            query_sql, 
            {"embedding": embedding_str, "top_k": 20}
        )
        rows = result.fetchall()
        
        context_chunks = [
            {
                "type": row[0],
                "id": row[1],
                "title": row[2],
                "description": row[3],
                "score": float(row[4])
            }
            for row in rows
        ]
        for c in context_chunks:
            print("-----------------------", c)
        
        return context_chunks


async def log_query_metrics(
    query_id: str,
    session_id: str,
    query_text: str,
    retrieved_chunks: List[Dict],
    llm_result: Dict,
    latency_retrieval_ms: int,
    latency_generation_ms: int,
    embedding_tokens: int
):
    """
    Enregistre métriques complètes dans retrieval_logs.
    """
    # Calcul coût embedding
    embedding_cost = (embedding_tokens * VOYAGE_PRICE_PER_MILLION) / 1_000_000
    
    # Construire JSONB chunks
    chunks_jsonb = [
        {"id": c["id"], "type": c["type"], "score": c["score"]}
        for c in retrieved_chunks
    ]
    
    total_cost = embedding_cost + llm_result["cost"]
    latency_total_ms = latency_retrieval_ms + latency_generation_ms
    
    async with AsyncSessionLocal() as db:
        insert_query = text("""
            INSERT INTO retrieval_logs (
                query_id, session_id, query_text, retrieved_chunks,
                retrieval_method, nb_chunks_retrieved,
                llm_provider, embedding_tokens, llm_tokens,
                embedding_cost, llm_cost, total_cost,
                latency_retrieval_ms, latency_generation_ms, latency_total_ms,
                latency_ms
            ) VALUES (
                :query_id, :session_id, :query_text, :retrieved_chunks,
                :retrieval_method, :nb_chunks_retrieved,
                :llm_provider, :embedding_tokens, :llm_tokens,
                :embedding_cost, :llm_cost, :total_cost,
                :latency_retrieval_ms, :latency_generation_ms, :latency_total_ms,
                :latency_ms
            )
        """)
        
        await db.execute(insert_query, {
            "query_id": query_id,
            "session_id": session_id,
            "query_text": query_text,
            "retrieved_chunks": str(chunks_jsonb).replace("'", '"'),  # JSON string
            "retrieval_method": "vector",
            "nb_chunks_retrieved": len(retrieved_chunks),
            "llm_provider": llm_result["provider_used"],
            "embedding_tokens": embedding_tokens,
            "llm_tokens": llm_result["tokens_used"],
            "embedding_cost": embedding_cost,
            "llm_cost": llm_result["cost"],
            "total_cost": total_cost,
            "latency_retrieval_ms": latency_retrieval_ms,
            "latency_generation_ms": latency_generation_ms,
            "latency_total_ms": latency_total_ms,
            "latency_ms": latency_total_ms  # Backward compat avec ancien schema
        })
        await db.commit()
    
    logger.info(
        f"📊 Query logged: {query_id} | "
        f"{len(retrieved_chunks)} chunks | "
        f"{llm_result['provider_used']} | "
        f"${total_cost:.6f} | {latency_total_ms}ms"
    )


async def update_session_metrics(
    session_id: str,
    total_cost: float,
    total_tokens: int,
    latency_ms: int,
    provider_used: str
):
    """
    Met à jour les métriques agrégées de la session.
    """
    async with AsyncSessionLocal() as db:
        # Récupérer stats actuelles
        select_query = text("""
            SELECT question_count, total_tokens, total_cost, 
                   avg_latency_ms, providers_used
            FROM chat_sessions
            WHERE session_id = :session_id
        """)
        result = await db.execute(select_query, {"session_id": session_id})
        row = result.fetchone()
        
        if not row:
            # Créer session si n'existe pas
            insert_query = text("""
                INSERT INTO chat_sessions (session_id, question_count, total_tokens, total_cost, avg_latency_ms, providers_used)
                VALUES (:session_id, 1, :total_tokens, :total_cost, :latency_ms, :providers_used)
            """)
            providers_used = {provider_used: 1}
            await db.execute(insert_query, {
                "session_id": session_id,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
                "latency_ms": latency_ms,
                "providers_used": str(providers_used).replace("'", '"')
            })
        else:
            # Mettre à jour session existante
            current_count, current_tokens, current_cost, current_avg_latency, providers_json = row
            
            new_count = current_count + 1
            new_tokens = current_tokens + total_tokens
            new_cost = float(current_cost) + total_cost
            
            # Moyenne latency
            new_avg_latency = ((current_avg_latency * current_count) + latency_ms) // new_count
            
            # Incrémenter provider count
            # providers_dict = eval(providers_json) if providers_json else {}
            providers_dict = providers_json if providers_json else {}
            providers_dict[provider_used] = providers_dict.get(provider_used, 0) + 1
            
            update_query = text("""
                UPDATE chat_sessions
                SET question_count = :new_count,
                    total_tokens = :new_tokens,
                    total_cost = :new_cost,
                    avg_latency_ms = :new_avg_latency,
                    providers_used = :providers_used
                WHERE session_id = :session_id
            """)
            await db.execute(update_query, {
                "session_id": session_id,
                "new_count": new_count,
                "new_tokens": new_tokens,
                "new_cost": new_cost,
                "new_avg_latency": new_avg_latency,
                # "providers_used": str(providers_dict).replace("'", '"'),
                "providers_used": json.dumps(providers_dict),
            })
        
        await db.commit()


async def rag_pipeline(
    question: str,
    session_id: str,
    top_k: int = 6,
    score_threshold: float = 0.7
) -> Dict:
    """
    Pipeline RAG complet avec logging.
    
    Returns:
        {
            "query_id": str,
            "response": str,
            "context_chunks": List[Dict],
            "tokens_used": int,
            "cost": float,
            "provider_used": str
        }
    """
    query_id = str(uuid.uuid4())
    
    # 1. Vectorisation + mesure latency
    logger.info(f"🔍 RAG Pipeline [{query_id}]: vectorizing...")
    start_retrieval = time.perf_counter()
    
    embedding = await vectorize_query(question)
    embedding_tokens = len(question.split())  # Approximation
    
    # 2. Recherche contexte
    context_chunks = await search_context(embedding, top_k)
    latency_retrieval_ms = int((time.perf_counter() - start_retrieval) * 1000)
    
    # Filtrer par score
    filtered_chunks = [
        chunk for chunk in context_chunks 
        if chunk['score'] >= score_threshold
    ]
    
    if not filtered_chunks:
        logger.warning(f"⚠️ No relevant context (threshold={score_threshold})")
        return {
            "query_id": query_id,
            "response": "Désolé, je n'ai pas trouvé d'information pertinente dans mon CV pour répondre à cette question.",
            "context_chunks": [],
            "tokens_used": 0,
            "cost": 0.0,
            "provider_used": "none"
        }
    
    # 3. Génération + mesure latency
    logger.info(f"✍️ RAG Pipeline [{query_id}]: generating with {len(filtered_chunks)} chunks...")
    start_generation = time.perf_counter()
    
    llm_result = await generate_response(question, filtered_chunks)
    latency_generation_ms = int((time.perf_counter() - start_generation) * 1000)
    
    # 4. Update session
    total_cost = (embedding_tokens * VOYAGE_PRICE_PER_MILLION / 1_000_000) + llm_result["cost"]
    total_tokens = embedding_tokens + llm_result["tokens_used"]
    latency_total_ms = latency_retrieval_ms + latency_generation_ms
    
    await update_session_metrics(
        session_id=session_id,
        total_cost=total_cost,
        total_tokens=total_tokens,
        latency_ms=latency_total_ms,
        provider_used=llm_result["provider_used"]
    )

    # 5. Logging métriques
    await log_query_metrics(
        query_id=query_id,
        session_id=session_id,
        query_text=question,
        retrieved_chunks=filtered_chunks,
        llm_result=llm_result,
        latency_retrieval_ms=latency_retrieval_ms,
        latency_generation_ms=latency_generation_ms,
        embedding_tokens=embedding_tokens
    )

    # 6. Logger les messages user/assistant
    await log_chat_messages(
        session_id=session_id,
        user_message=question,
        assistant_response=llm_result["response"],
        tokens_used=total_tokens
    )
    
    return {
        "query_id": query_id,
        "response": llm_result["response"],
        "context_chunks": filtered_chunks,
        "tokens_used": total_tokens,
        "cost": total_cost,
        "provider_used": llm_result["provider_used"]
    }

async def log_chat_messages(
    session_id: str,
    user_message: str,
    assistant_response: str,
    tokens_used: int
):
    """
    Enregistre l'échange user/assistant dans chat_messages.
    """
    async with AsyncSessionLocal() as db:
        # Message user
        await db.execute(text("""
            INSERT INTO chat_messages (session_id, role, content, tokens_used)
            VALUES (:session_id, 'user', :content, 0)
        """), {"session_id": session_id, "content": user_message})
        
        # Message assistant
        await db.execute(text("""
            INSERT INTO chat_messages (session_id, role, content, tokens_used)
            VALUES (:session_id, 'assistant', :content, :tokens_used)
        """), {"session_id": session_id, "content": assistant_response, "tokens_used": tokens_used})
        
        await db.commit()
    
    logger.info(f"💬 Messages logged for session {session_id}")