"""User sql models"""
class UserModel:
    def __init__(self, name: str, goal: str):
        self.name = name
        self.goal = goal

    def to_dict(self) -> dict:
        return {"name": self.name, "goal": self.goal}
