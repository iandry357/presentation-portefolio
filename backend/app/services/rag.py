"""
Pipeline RAG avec logging complet des métriques.
"""
import time
import uuid
from typing import List, Dict
from app.core.database import AsyncSessionLocal
from app.services.embeddings import vectorize_query
from app.services.llm import generate_response
from app.core.llm_client import generate_with_fallback
from sqlalchemy import text
import logging
import json
from app.services.embeddings import rerank_chunks
from rank_bm25 import BM25Okapi
from app.services.job_profile import build_profile_text

logger = logging.getLogger(__name__)

# Pricing Voyage AI
VOYAGE_PRICE_PER_MILLION = 0.13

async def search_context(query: str, embedding: List[float], top_k: int = 15) -> List[Dict]:
    """
    Hybrid Search : cosinus pgvector + BM25 fusionnés via RRF.
    """
    async with AsyncSessionLocal() as db:
        # --- Chargement complet des chunks pour BM25 ---
        rows_all = await db.execute(text("""
            SELECT 'experience' as type, experiences.id,
                role as title,
                TO_CHAR(experiences.start_date, 'YYYY-MM-DD') || ' à ' || TO_CHAR(experiences.end_date, 'YYYY-MM-DD') || ' description : ' || context || ' ' || objective || ' ' || problem || ' ' || solution || ' ' || results || ' ' || impact || ' ' || description || ' ' || stack || ' ' || collaborators as description
            FROM experiences
            LEFT JOIN projects ON experiences.id = projects.experience_id
            WHERE experiences.embedding IS NOT NULL
            UNION ALL
            SELECT 'formation', id, degree,
                TO_CHAR(start_date, 'YYYY-MM-DD') || ' à ' || TO_CHAR(end_date, 'YYYY-MM-DD') || ' description ' || description || ' ' || fields || ' ' || key_learnings
            FROM formations WHERE embedding IS NOT NULL
            UNION ALL
            SELECT 'information', id,
                'je suis ' || prenom || ' ' || nom || ' avec le prenom prononcé ' || prononciation || ' né à ' || pays_naissance || ' le ' || TO_CHAR(date_naissance, 'YYYY-MM-DD'),
                'Passioné depuis par les sciences dures et les nouvelles technologies, aussi je suis ' || passion
            FROM informations WHERE embedding IS NOT NULL
        """))
        all_chunks = [
            {"type": r[0], "id": r[1], "title": r[2], "description": r[3], "cid": f"{r[0]}_{r[1]}"}
            for r in rows_all.fetchall()
        ]

        # --- Score vectoriel pgvector ---
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        rows_vec = await db.execute(text("""
            SELECT id, 1 - (embedding <=> CAST(:emb AS vector)) as score
            FROM (
                SELECT experiences.id, experiences.embedding FROM experiences
                LEFT JOIN projects ON experiences.id = projects.experience_id
                WHERE experiences.embedding IS NOT NULL
                UNION ALL
                SELECT id, embedding FROM formations WHERE embedding IS NOT NULL
                UNION ALL
                SELECT id, embedding FROM informations WHERE embedding IS NOT NULL
            ) sub
            ORDER BY score DESC
            LIMIT :top_k
        """), {"emb": embedding_str, "top_k": top_k})
        # vec_ranks = {r[0]: i for i, r in enumerate(rows_vec.fetchall())}
        vec_ranks = {f"{r[0]}_{r[1]}": i for i, r in enumerate(rows_vec.fetchall())}

    # --- Score BM25 ---
    corpus = [c["description"].lower().split() for c in all_chunks]
    bm25 = BM25Okapi(corpus)
    bm25_scores = bm25.get_scores(query.lower().split())
    bm25_ranked = sorted(range(len(all_chunks)), key=lambda i: bm25_scores[i], reverse=True)
    # bm25_ranks = {all_chunks[i]["id"]: rank for rank, i in enumerate(bm25_ranked)}
    bm25_ranks = {all_chunks[i]["cid"]: rank for rank, i in enumerate(bm25_ranked)}

    # --- Fusion RRF (k=60 standard) ---
    K = 60
    rrf_scores = {}
    for chunk in all_chunks:
        cid = chunk["cid"]
        rank_vec = vec_ranks.get(cid, len(all_chunks))
        rank_bm25 = bm25_ranks.get(cid, len(all_chunks))
        rrf_scores[cid] = (1 / (K + rank_vec)) + (1 / (K + rank_bm25))

    # --- Tri final + reconstruction chunks ---
    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]
    id_to_chunk = {c["cid"]: c for c in all_chunks}

    result = []
    for cid in sorted_ids:
        if cid in id_to_chunk:
            chunk = id_to_chunk[cid].copy()
            chunk["score"] = round(rrf_scores[cid], 6)
            result.append(chunk)

    logger.info(f"🔍 Hybrid search: {len(result)} chunks (BM25+cosinus RRF)")
    return result

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
            "retrieval_method": "vector+rerank",
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

async def fetch_conversation_history(session_id: str, limit: int = 6) -> List[Dict]:
    """
    Récupère les N derniers messages de la session pour la mémoire conversationnelle.
    Retourne une liste ordonnée du plus ancien au plus récent.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT role, content FROM chat_messages
                WHERE session_id = :sid
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"sid": session_id, "limit": limit}
        )
        rows = result.fetchall()

    # DESC en DB → on reverse pour avoir ordre chronologique
    history = [{"role": row[0], "content": row[1]} for row in reversed(rows)]
    logger.info(f"📜 History loaded: {len(history)} messages for session {session_id}")
    return history

async def summarize_history(history: List[Dict]) -> str:
    """
    Compresse l'historique conversationnel en un résumé court via Groq.
    Retourne une string vide si pas d'historique.
    """
    if not history:
        return ""

    exchanges = "\n".join([f"{m['role']}: {m['content']}" for m in history])

    result = await generate_with_fallback(
        system_prompt="Tu résumes en 2-3 phrases maximum les échanges d'une conversation. Garde uniquement les sujets abordés et les informations mentionnées. Ne réponds qu'avec le résumé, rien d'autre.",
        user_prompt=exchanges,
        models=["groq"],
        max_tokens=200,
        temperature=0.1
    )
    logger.info(f"📝 History summarized: {result['tokens_used']} tokens")
    return result["response"]

async def analyze_question(question: str) -> Dict:
    """
    Classifie la question : GENERAL ou SPECIFIC.
    GENERAL → résumé profil direct
    SPECIFIC → pipeline hybrid search + rerank avec historique enrichi
    """
    # context_block = f"Résumé conversation précédente : {history_summary}" if history_summary else "Pas de conversation précédente."
    context_block = f" "

    result = await generate_with_fallback(
        system_prompt="""Tu es un classificateur. Réponds UNIQUEMENT en JSON valide sans markdown.
{"type": "GENERAL" ou "SPECIFIC"}

GENERAL = présentation globale, question sociale, demande de résumé complet.
Exemples : "présente-toi", "tu fais quoi", "c'est quoi ton parcours", "bonjour".

SPECIFIC = toute autre question : expérience, technologie, date, entreprise,
période temporelle, continuité d'un sujet précédent.
Exemples : "et avant ça ?", "tu as utilisé Python ?", "c'était quand ?", "tu y es resté combien de temps ?".""",
        # user_prompt=f"{context_block}\n\nQuestion : {question}",
        user_prompt=question,
        models=["groq"],
        max_tokens=30,
        temperature=0.0
    )

    try:
        parsed = json.loads(result["response"])
        q_type = parsed.get("type", "SPECIFIC").upper()
        if q_type not in ["GENERAL", "SPECIFIC"]:
            q_type = "SPECIFIC"
    except Exception:
        logger.warning("⚠️ analyze_question parse failed, fallback SPECIFIC")
        q_type = "SPECIFIC"

    logger.info(f"🔀 Question analyzed: type={q_type}")
    return {"type": q_type}

async def reformulate_question(question: str, history_summary: str) -> str:
    """
    Reformule une question de continuité en question autonome
    exploitable par la recherche vectorielle.
    """
    result = await generate_with_fallback(
        system_prompt="""Tu reformules une question vague en question explicite et autonome,
en utilisant le contexte de la conversation précédente.
Réponds UNIQUEMENT avec la question reformulée, rien d'autre.""",
        user_prompt=f"Conversation précédente : {history_summary}\n\nQuestion à reformuler : {question}",
        models=["groq"],
        max_tokens=50,
        temperature=0.0
    )
    reformulated = result["response"].strip()
    logger.info(f"✏️ Reformulated: '{question}' → '{reformulated}'")
    return reformulated

async def rag_pipeline(
    question: str,
    session_id: str,
    top_k: int = 15
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
    modelEmbeddings = "voyage"
    # modelEmbeddings = "mistral"
    
    # query_type = await classify_question(question)

    # if query_type == "GENERAL":
    #     async with AsyncSessionLocal() as db:
    #         profile_text = await build_profile_text(db)
    #     filtered_chunks = [{
    #         "type": "profile",
    #         "id": 0,
    #         "title": "Résumé profil",
    #         "description": profile_text,
    #         "score": 1.0
    #     }]
    #     logger.info("🗺️ GENERAL question → résumé profil direct")
    # else:
    #     embedding = await vectorize_query(question, modelEmbeddings)
    #     context_chunks = await search_context(question, embedding, top_k)
    #     filtered_chunks = await rerank_chunks(question, context_chunks, top_k=5)
    history = await fetch_conversation_history(session_id)
    history_summary = await summarize_history(history)

    analysis = await analyze_question(question)

    if analysis["type"] == "GENERAL":
        async with AsyncSessionLocal() as db:
            profile_text = await build_profile_text(db)
        filtered_chunks = [{
            "type": "profile",
            "id": 0,
            "title": "Résumé profil",
            "description": profile_text,
            "score": 1.0
        }]
        logger.info("🗺️ GENERAL → résumé profil direct")
    else:
        # Approche 1 — enrichissement systématique avant embedding
        search_question = f"{question} {history_summary}".strip() if history_summary else question
        logger.info(f"🔍 Search question enrichie: '{search_question[:100]}...'")

        embedding = await vectorize_query(search_question, modelEmbeddings)
        context_chunks = await search_context(search_question, embedding, top_k)
        filtered_chunks = await rerank_chunks(search_question, context_chunks, top_k=5)

    embedding_tokens = len(question.split())
    latency_retrieval_ms = int((time.perf_counter() - start_retrieval) * 1000)
    
    if not filtered_chunks:
        logger.warning(f"⚠️ No relevant context founded")
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

    # Récupérer historique conversationnel
    # history = await fetch_conversation_history(session_id)
    # llm_result = await generate_response(question, filtered_chunks, history)
    # history = await fetch_conversation_history(session_id)
    # history_summary = await summarize_history(history)
    llm_result = await generate_response(question, filtered_chunks, history_summary)
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