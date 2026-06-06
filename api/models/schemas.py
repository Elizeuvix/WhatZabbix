from pydantic import BaseModel, Field
from typing import Optional


# ─── Messages ────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    number: str = Field(
        ...,
        description="Número com DDI (ex: 5511999999999)",
        examples=["5511999999999"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Texto da mensagem",
    )


class SendGroupMessageRequest(BaseModel):
    group_id: str = Field(
        ...,
        description="ID do grupo WhatsApp (ex: 120363xxxxxxxx@g.us)",
        examples=["120363000000000000@g.us"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Texto da mensagem",
    )


class MessageResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


# ─── Zabbix ──────────────────────────────────────────────────────────────────

class ZabbixAlertRequest(BaseModel):
    to: str = Field(
        ...,
        description="Número de telefone ou ID do grupo de destino",
    )
    subject: str = Field(..., description="Assunto do alerta (vem do {ALERT.SUBJECT})")
    body: str = Field(..., description="Corpo do alerta (vem do {ALERT.MESSAGE})")

    # Campos opcionais que enriquecem a mensagem formatada
    severity: Optional[str] = Field(
        None,
        description="Severidade textual: Not classified, Information, Warning, Average, High, Disaster",
    )
    event_nseverity: Optional[str] = Field(
        None,
        description="Severidade numérica Zabbix: 0=Not classified, 1=Info, 2=Warning, 3=Average, 4=High, 5=Disaster",
    )
    status: Optional[str] = Field(
        None,
        description="PROBLEM ou RESOLVED",
    )
    event_value: Optional[str] = Field(
        None,
        description="0 = OK/Resolved, 1 = Problem",
    )
    event_update_status: Optional[str] = Field(
        None,
        description="1 = evento atualizado/acknowledged",
    )
    event_id: Optional[str] = Field(None, description="ID do evento Zabbix")
    trigger_name: Optional[str] = Field(None, description="Nome do trigger")
    host: Optional[str] = Field(None, description="Host afetado")
    event_date: Optional[str] = Field(None, description="Data do evento (DD/MM/YYYY)")
    event_time: Optional[str] = Field(None, description="Hora do evento (HH:MM:SS)")
    zabbix_url: Optional[str] = Field(
        None,
        description="URL base do Zabbix para gerar link do evento (ex: http://zabbix.local/)",
    )
    is_group: bool = Field(False, description="Definir true se 'to' for um ID de grupo")
