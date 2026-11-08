"""Exceptions métier. Leurs messages sont destinés à l'utilisateur (en français)."""


class AcademicWriterError(Exception):
    """Erreur de base de l'application."""


class NotFoundError(AcademicWriterError):
    """Objet introuvable (projet, document, fichier)."""


class ValidationFailed(AcademicWriterError):
    """Donnée invalide ou opération non permise dans l'état actuel."""


class SecurityViolation(AcademicWriterError):
    """Opération refusée pour raison de sécurité (chemin, fichier suspect...)."""


class ConflictError(AcademicWriterError):
    """Conflit avec l'état existant."""


class StorageError(AcademicWriterError):
    """Erreur de la base de données ou du stockage local."""
