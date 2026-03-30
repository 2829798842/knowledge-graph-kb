"""FastAPI dependency helpers for the knowledge-base container."""
from fastapi import HTTPException, Request

from src.kb import KnowledgeBaseContainer


def get_kb_container(request: Request) -> KnowledgeBaseContainer:
    container = getattr(request.app.state, "kb_container", None)
    if container is None:
        raise HTTPException(status_code=503, detail="Knowledge-base container is not initialized yet.")
    return container


def get_model_config_service(request: Request):
    return get_kb_container(request).model_config_service


def get_import_service(request: Request):
    return get_kb_container(request).import_service


def get_record_search_service(request: Request):
    return get_kb_container(request).record_search_service


def get_entity_search_service(request: Request):
    return get_kb_container(request).entity_search_service


def get_relation_search_service(request: Request):
    return get_kb_container(request).relation_search_service


def get_source_search_service(request: Request):
    return get_kb_container(request).source_search_service


def get_conversation_service(request: Request):
    return get_kb_container(request).conversation_service


def get_graph_service(request: Request):
    return get_kb_container(request).graph_service


def get_source_service(request: Request):
    return get_kb_container(request).source_service


def get_openai_gateway(request: Request):
    return get_kb_container(request).openai_gateway


def get_maintenance_service(request: Request):
    return get_kb_container(request).maintenance_service
