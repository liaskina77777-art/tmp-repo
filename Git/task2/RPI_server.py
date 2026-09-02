#!/usr/bin/env python3
"""
FastAPI сервер для предсказания взаимодействия РНК и белка.

Эндпоинты:
- GET /proteins: возвращает список поддерживаемых белков
- POST /predict: предсказывает скор взаимодействия для пар РНК-белок
"""

import os
import re
from typing import List, Dict, Optional, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator
from typing_extensions import Annotated

# Импортируем функции для работы с данными
from data_generator import load_dataset, generate_dataset, PROTEINS

# ============== Pydantic модели данных ==============

class PredictionRequest(BaseModel):
    """Модель запроса для предсказания."""
    protein: str = Field(..., description="Мнемоника белка (например, EZH2)")
    gene_name: str = Field(..., description="Название гена (например, HOTAIR)")
    sequence: str = Field(..., description="Последовательность РНК (A, T, G, C, U)")
    
    @validator('sequence')
    def validate_sequence(cls, v):
        """Валидатор для последовательности."""
        if not v or len(v) == 0:
            raise ValueError("Sequence cannot be empty")
        allowed = set('ATGCUatgcu')
        if not all(c in allowed for c in v):
            raise ValueError(f"Invalid characters in sequence. Allowed: A, T, G, C, U")
        return v.upper()
    
    @validator('protein')
    def validate_protein(cls, v):
        """Валидатор для имени белка."""
        if not v or len(v) == 0:
            raise ValueError("Protein name cannot be empty")
        return v.upper()
    
    class Config:
        json_schema_extra = {
            "example": {
                "protein": "EZH2",
                "gene_name": "HOTAIR",
                "sequence": "AGTGGAGCAGTGAGTG"
            }
        }


class PredictionResponse(BaseModel):
    """Модель ответа для предсказания."""
    protein: str = Field(..., description="Мнемоника белка")
    gene_name: str = Field(..., description="Название гена")
    score: Optional[float] = Field(None, description="Предсказанный скор взаимодействия")
    notes: Optional[str] = Field(None, description="Дополнительная информация (ошибки, предупреждения)")
    converted_u_to_t: Optional[bool] = Field(False, description="Была ли конвертация U->T")
    original_sequence: Optional[str] = Field(None, description="Исходная последовательность")
    
    class Config:
        json_schema_extra = {
            "example": {
                "protein": "EZH2",
                "gene_name": "HOTAIR",
                "score": -0.15,
                "notes": None,
                "converted_u_to_t": False,
                "original_sequence": None
            }
        }


class ProteinsResponse(BaseModel):
    """Модель ответа для списка белков."""
    proteins: List[str] = Field(..., description="Список поддерживаемых белков")
    count: int = Field(..., description="Количество белков")
    
    class Config:
        json_schema_extra = {
            "example": {
                "proteins": ["EZH2", "SUZ12", "CTCF"],
                "count": 3
            }
        }


class BatchPredictionRequest(BaseModel):
    """Модель для батчевого запроса предсказаний."""
    requests: List[PredictionRequest] = Field(..., description="Список запросов на предсказание")
    
    @validator('requests')
    def validate_not_empty(cls, v):
        if not v:
            raise ValueError("Requests list cannot be empty")
        return v


# ============== Инициализация приложения ==============

# Загружаем данные (генерируем если не существует)
DATA_PATH = "data/rna_protein_scores.json"

def initialize_data():
    """Инициализирует данные для сервера."""
    if not os.path.exists(DATA_PATH):
        print("Data file not found. Generating new dataset...")
        from data_generator import generate_dataset, PROTEINS
        generate_dataset(PROTEINS)
    
    return load_dataset(DATA_PATH)


# Глобальная переменная для хранения данных
RNA_PROTEIN_DATA = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan контекстный менеджер для загрузки данных при старте."""
    global RNA_PROTEIN_DATA
    print("Loading RNA-protein interaction data...")
    RNA_PROTEIN_DATA = initialize_data()
    print(f"Loaded data for {len(RNA_PROTEIN_DATA)} proteins")
    print(f"Total motifs: {sum(len(motifs) for motifs in RNA_PROTEIN_DATA.values())}")
    yield
    print("Shutting down...")


# Создаем приложение FastAPI
app = FastAPI(
    title="RNA-Protein Interaction Predictor",
    description="""
    API для предсказания взаимодействия между РНК и белками.
    
    ## Возможности:
    - Получение списка поддерживаемых белков
    - Предсказание скора взаимодействия для пар РНК-белок
    - Автоматическая конвертация U → T в РНК последовательностях
    - Подробные сообщения об ошибках
    
    ## Как это работает:
    Для каждой пары (белок, РНК) API ищет известные мотивы РНК для указанного белка
    и суммирует их скоры. Если мотивов нет, возвращается None.
    """,
    version="1.0.0",
    contact={
        "name": "Bioinformatics Group",
        "email": "bioinfo@example.com",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan
)


def convert_u_to_t(sequence: str) -> tuple[str, bool]:
    """
    Конвертирует U в T в последовательности РНК.
    
    Returns:
        tuple: (конвертированная последовательность, был ли флаг конвертации)
    """
    if 'U' in sequence:
        return sequence.replace('U', 'T'), True
    return sequence, False


def compute_score(protein: str, sequence: str) -> Optional[float]:
    """
    Вычисляет скор взаимодействия для белка и РНК.
    
    Args:
        protein: мнемоника белка
        sequence: последовательность РНК
    
    Returns:
        float: сумма скоров найденных мотивов, или None если мотивов нет
    """
    if protein not in RNA_PROTEIN_DATA:
        return None
    
    protein_motifs = RNA_PROTEIN_DATA[protein]
    total_score = 0.0
    found_any = False
    
    # Ищем все мотивы, которые встречаются в последовательности
    for motif, score in protein_motifs.items():
        if motif in sequence:
            total_score += score
            found_any = True
    
    return round(total_score, 4) if found_any else None


# ============== Эндпоинты API ==============

@app.get(
    "/proteins",
    response_model=ProteinsResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить список белков",
    description="Возвращает список всех белков, для которых доступно предсказание взаимодействия.",
    tags=["Information"]
)
async def get_proteins():
    """
    GET эндпоинт для получения списка поддерживаемых белков.
    
    Returns:
        ProteinsResponse: Объект со списком белков и их количеством
    """
    proteins_list = list(RNA_PROTEIN_DATA.keys())
    return ProteinsResponse(proteins=proteins_list, count=len(proteins_list))


@app.post(
    "/predict",
    response_model=List[PredictionResponse],
    status_code=status.HTTP_200_OK,
    summary="Предсказать взаимодействие",
    description="Предсказывает скор взаимодействия для одной или нескольких пар РНК-белок.",
    tags=["Prediction"]
)
async def predict_interactions(
    requests: Union[PredictionRequest, List[PredictionRequest]]
):
    """
    POST эндпоинт для предсказания взаимодействия.
    
    Принимает либо один объект запроса, либо список запросов.
    
    Args:
        requests: Один запрос или список запросов
    
    Returns:
        List[PredictionResponse]: Список ответов для каждого запроса
    """
    # Приводим к списку, если пришел один запрос
    if isinstance(requests, PredictionRequest):
        requests_list = [requests]
    else:
        requests_list = requests
    
    responses = []
    
    for req in requests_list:
        # Конвертируем U в T
        converted_seq, was_converted = convert_u_to_t(req.sequence)
        
        # Проверяем существование белка в базе
        if req.protein not in RNA_PROTEIN_DATA:
            responses.append(PredictionResponse(
                protein=req.protein,
                gene_name=req.gene_name,
                score=None,
                notes=f"Error: No such protein '{req.protein}' in database",
                converted_u_to_t=was_converted,
                original_sequence=req.sequence if was_converted else None
            ))
            continue
        
        # Вычисляем скор
        score = compute_score(req.protein, converted_seq)
        
        # Формируем заметку, если скор None
        notes = None
        if score is None:
            notes = f"Warning: No known motifs found in sequence for protein '{req.protein}'"
        
        responses.append(PredictionResponse(
            protein=req.protein,
            gene_name=req.gene_name,
            score=score,
            notes=notes,
            converted_u_to_t=was_converted,
            original_sequence=req.sequence if was_converted else None
        ))
    
    return responses


# Дополнительный эндпоинт для проверки здоровья сервера
@app.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Проверка состояния сервера",
    tags=["System"]
)
async def health_check():
    """Проверяет, что сервер работает и данные загружены."""
    return {
        "status": "healthy",
        "proteins_loaded": len(RNA_PROTEIN_DATA),
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "RPI_server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
