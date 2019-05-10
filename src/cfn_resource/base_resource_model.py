class BaseResourceModel:

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def new(cls, **resource_model):
        return cls(**resource_model)
