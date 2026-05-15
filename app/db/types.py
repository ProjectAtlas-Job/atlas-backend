from pgvector.sqlalchemy import VECTOR


class Vector(VECTOR):
    def __init__(self, dimensions: int) -> None:
        super().__init__(dim=dimensions)
        self.dimensions = dimensions
