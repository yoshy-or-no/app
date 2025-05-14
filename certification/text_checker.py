from difflib import SequenceMatcher
import re
import json

class TextAnswerChecker:
    def __init__(self, correct_answer, similarity_threshold=0.8, synonyms=None, abbreviations=None):
        self.correct_answer = correct_answer
        self.similarity_threshold = similarity_threshold
        self.synonyms = synonyms or {}
        self.abbreviations = abbreviations or {}
        self.normalized_correct = self._normalize_text(correct_answer)
    
    def _normalize_text(self, text):
        if not text:
            return ""
        # Приведение к нижнему регистру
        text = text.lower()
        # Удаление лишних пробелов
        text = ' '.join(text.split())
        # Удаление знаков препинания, кроме букв, цифр и пробелов
        text = re.sub(r'[^\w\s]', '', text)
        return text
    
    def _expand_abbreviations(self, text):
        # Замена аббревиатур на полные формы
        for abbr, full in self.abbreviations.items():
            text = text.replace(abbr.lower(), full.lower())
        return text
    
    def _expand_synonyms(self, text):
        # Замена синонимов
        for synonym, main in self.synonyms.items():
            text = text.replace(synonym.lower(), main.lower())
        return text
    
    def _calculate_similarity(self, text1, text2):
        return SequenceMatcher(None, text1, text2).ratio()
    
    def check_answer(self, user_answer):
        # Сначала проверяем точное совпадение (как в текущей системе)
        if user_answer.lower() == self.correct_answer.lower():
            return True
        
        # Нормализуем ответ пользователя
        normalized_user = self._normalize_text(user_answer)
        
        # Расширяем аббревиатуры и синонимы
        expanded_user = self._expand_abbreviations(normalized_user)
        expanded_user = self._expand_synonyms(expanded_user)
        
        # Проверяем схожесть с правильным ответом
        similarity = self._calculate_similarity(expanded_user, self.normalized_correct)
        return similarity >= self.similarity_threshold 