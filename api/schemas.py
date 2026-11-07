"""Modelos de entrada/salida. Pydantic valida tipos, largos y valores permitidos (si falla -> HTTP 422)."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Genero(str, Enum):
    femenino = "Femenino"
    masculino = "Masculino"
    otro = "Otro"


class Dispositivo(str, Enum):
    movil = "Móvil"
    desktop = "Desktop"
    tablet = "Tablet"


class Categoria(str, Enum):
    tecnologia = "Tecnología"
    cultura = "Cultura"
    educacion = "Educación"
    deportes = "Deportes"
    entretenimiento = "Entretenimiento"


class TipoPublicacion(str, Enum):
    imagen = "Imagen"
    video = "Video"
    texto = "Texto"


class TipoReaccion(str, Enum):
    me_gusta = "Me gusta"
    me_encanta = "Me encanta"
    me_entristece = "Me entristece"
    me_enoja = "Me enoja"


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)


# ----------------------------------------------------------------- usuarios
class UsuarioCrear(Base):
    nombre: str = Field(min_length=2, max_length=80, examples=["Camila Rojas"])
    correo: EmailStr = Field(examples=["camila.rojas@contentflow.cl"])
    pais: str = Field(min_length=2, max_length=60, examples=["Chile"])
    genero: Genero
    dispositivo: Dispositivo


class UsuarioActualizar(Base):
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    correo: EmailStr | None = None
    pais: str | None = Field(default=None, min_length=2, max_length=60)
    genero: Genero | None = None
    dispositivo: Dispositivo | None = None


# ----------------------------------------------------------------- publicaciones
def limpiar_hashtags(v: list[str]) -> list[str]:
    """Pasa a minúsculas, exige '#', sin espacios y sin repetidos."""
    limpios = []
    for h in v:
        h = h.strip().lower()
        if not h.startswith("#") or len(h) < 2 or " " in h:
            raise ValueError(f"hashtag inválido: '{h}' (debe empezar con # y no tener espacios)")
        if h not in limpios:
            limpios.append(h)
    return limpios


class PublicacionCrear(Base):
    usuario_id: str = Field(pattern=r"^user_\d+$", examples=["user_10"])
    contenido: str = Field(min_length=1, max_length=2000)
    categoria: Categoria
    tipo: TipoPublicacion
    hashtags: list[str] = Field(default_factory=list, max_length=10, examples=[["#innovacion"]])

    @field_validator("hashtags")
    @classmethod
    def validar_hashtags(cls, v):
        return limpiar_hashtags(v)


class PublicacionActualizar(Base):
    contenido: str | None = Field(default=None, min_length=1, max_length=2000)
    categoria: Categoria | None = None
    tipo: TipoPublicacion | None = None
    hashtags: list[str] | None = Field(default=None, max_length=10)

    @field_validator("hashtags")
    @classmethod
    def validar_hashtags(cls, v):
        return limpiar_hashtags(v) if v is not None else v


# ----------------------------------------------------------------- interacciones
class ReaccionCrear(Base):
    usuario_id: str = Field(pattern=r"^user_\d+$")
    publicacion_id: str = Field(pattern=r"^pub_\d+$")
    tipo_reaccion: TipoReaccion


class ComentarioCrear(Base):
    usuario_id: str = Field(pattern=r"^user_\d+$")
    publicacion_id: str = Field(pattern=r"^pub_\d+$")
    comentario: str = Field(min_length=1, max_length=500)


class ComentarioLikes(Base):
    incremento: int = Field(default=1, ge=1, le=1000, description="Cuántos likes sumar")


# ----------------------------------------------------------------- respuestas
class Mensaje(BaseModel):
    mensaje: str
    detalle: dict | None = None


class SaludAPI(BaseModel):
    estado: str
    base_datos: str
    latencia_ms: float
    fecha: datetime
