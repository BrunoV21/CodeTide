
from pydantic import BaseModel, RootModel
from typing import Dict, List, Optional

class Step(BaseModel):
    step :int
    description :str
    instructions :str
    context_identifiers :Optional[List[str]]=None

class Steps(RootModel):
    root :List[Step]

    @classmethod
    def from_steps(cls, steps :List[Dict])->"Steps":
        return cls(root=[Step(**kwargs) for kwargs in steps])