from mongoengine import (
    EmbeddedDocumentField,
    EmbeddedDocumentListField,
    ListField,
    StringField,
)
from rest_framework_mongoengine import fields as fields

from api.v4.serializers import (
    CustomDocumentSerializer,
    CustomEmbeddedDocumentSerializer,
)
from app.personnel.models.denormalization.worker import WorkerDenormalized
from app.tickets.models.support import (
    DepartmentProviderEmbedded,
    SupportTicket,
    SupportTicketMessage,
    TicketCreatorEmbedded,
)
from processing.models.billing.files import Files

FIELDS = (
    "id",
    "type",
    "_type",
    "subject",
    "str_number",
    "owner",
    "author",
    "status",
    "initial",
    "executor",
    "spectators",
    "created_by",
    "redmine",
    "metadata",
    "mobile_app",
)

FIELDS_NOT_AUTH = (
    "id",
    "type",
    "_type",
    "subject",
    "str_number",
    "owner",
    "author",
    "status",
    "initial",
    "spectators",
    "created_by",
    "redmine",
    "metadata",
    "mobile_app",
)


class InitialEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)
    body = fields.body = StringField()
    author = fields.ObjectIdField()
    files = EmbeddedDocumentListField(Files)

    class Meta:
        model = SupportTicketMessage
        fields = ("id", "body", "author", "files")


class CreatedbyEmbeddedSerializer(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)
    department = EmbeddedDocumentField(DepartmentProviderEmbedded)
    _type = ListField(StringField())

    class Meta:
        model = TicketCreatorEmbedded
        fields = (
            "id",
            "department",
            "_type",
        )


class ExecutorEmbeddedSerialized(CustomEmbeddedDocumentSerializer):
    id = fields.ObjectIdField()

    class Meta:
        model = WorkerDenormalized
        fields = ("id",)


class SupportTicketSerializer(CustomDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)

    class Meta:
        model = SupportTicket
        fields = FIELDS


class SupportTicketNotAuthSerializer(CustomDocumentSerializer):
    id = fields.ObjectIdField(read_only=False)

    class Meta:
        model = SupportTicket
        fields = FIELDS_NOT_AUTH


class SupportTicketCreateSerializer(CustomDocumentSerializer):
    initial = InitialEmbeddedSerializer(required=True)
    created_by = CreatedbyEmbeddedSerializer(required=True)

    class Meta:
        model = SupportTicket
        fields = FIELDS
        read_only_fields = ("mobile_app",)


class SupportTicketUpdateSerializer(CustomDocumentSerializer):
    executor = ExecutorEmbeddedSerialized()

    class Meta:
        model = SupportTicket
        fields = FIELDS
        read_only_fields = ("mobile_app",)


class SupportTicketListSerializer(CustomDocumentSerializer):
    class Meta:
        model = SupportTicket
        fields = FIELDS + ("comments",)


class SupportTicketNotAuthListSerializer(CustomDocumentSerializer):
    class Meta:
        model = SupportTicket
        fields = FIELDS_NOT_AUTH + ("comments",)


class SupportTicketCommentsSerializer(CustomDocumentSerializer):
    class Meta:
        model = SupportTicket
        fields = FIELDS + ("comments",)


class TicketCommentSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = SupportTicketMessage
        fields = "__all__"


class TicketCommentPatchSerializer(CustomEmbeddedDocumentSerializer):
    class Meta:
        model = SupportTicketMessage
        fields = ("is_published",)
