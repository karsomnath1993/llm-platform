from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    prompt : str = Field(min_length = 1, max_length = 4000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    
class ChatResponse(BaseModel):
    response: str
    model: str