from app.services.ai_classifier import AIClassifier


class IntentService:
    def __init__(self, classifier: AIClassifier) -> None:
        self.classifier = classifier

    async def classify(self, text: str) -> str:
        return await self.classifier.classify_intent(text)
