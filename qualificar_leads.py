"""Qualificador de leads imobiliários com a API do Claude.

Lê as mensagens de leads em leads.csv, pede ao modelo uma qualificação
em formato fixo e grava os resultados em resultados.csv, ordenados
por prioridade.
"""

import csv
import os
from typing import Literal, Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

ARQUIVO_ENTRADA = "leads.csv"
ARQUIVO_SAIDA = "resultados.csv"
MODELO = "claude-haiku-5-5"

# Regras de negócio enviadas como prompt de sistema em toda chamada.
# É aqui que se ajusta o comportamento do modelo sem mexer no código.
INSTRUCOES = """Você é um assistente de pré-vendas de uma imobiliária brasileira.
Sua tarefa é qualificar leads a partir da primeira mensagem que eles enviaram.

Regras:
- Nunca invente informação. Se a mensagem não diz algo, use null.
- Você pode deduzir a operação pelo orçamento: valor total (como 600 mil ou 1.2mi)
  indica compra; valor por mês indica aluguel. Isso é dedução, não invenção.
- A urgência é alta quando o lead cita prazo curto (dias, semanas, poucos meses,
  até o fim do ano) ou escreve que é urgente.
- Copie o orçamento como o lead escreveu, sem converter nem arredondar.
- A localização é onde o lead quer o imóvel. Ignore outros lugares citados,
  como o endereço de um imóvel oferecido em permuta.
- Responda sempre em português, mesmo que o lead escreva em outro idioma.
- Quem quer vender o próprio imóvel é um lead válido para a captação de imóveis.
- Lead em atendimento sem retorno tem urgência alta, porque há risco de perder o cliente.
- Prioridade vai de 1 a 5. Avalie de cima para baixo e use a primeira que se aplicar:
  1 = não é cliente (spam, parceiro comercial, elogio ou comentário sem pedido)
  5 = lead que já está em atendimento e reclama de falta de retorno
  5 = tem os três: sabe se quer comprar ou alugar, informou orçamento e tem urgência alta
  4 = sabe se quer comprar, alugar ou vender, mas falta orçamento ou a urgência não é alta
  3 = interesse real, mas ainda não sabe se compra ou aluga
  2 = mensagem vaga demais para saber o que a pessoa quer
- A próxima ação deve ser concreta e curta, como algo que o corretor faria hoje.
"""


class LeadQualificado(BaseModel):
    """Formato da resposta do modelo para cada lead.

    O Pydantic valida os campos e gera o esquema JSON que vai na requisição.
    As descrições de cada campo vão junto no esquema e o modelo lê como instrução.
    """

    tipo_contato: Literal[
        "comprador", "locatario", "investidor", "vendedor",
        "parceiro", "spam", "indefinido",
    ]
    operacao: Literal["compra", "aluguel", "venda", "indefinida"]

    # Optional permite null quando o lead não informou o dado
    tipo_imovel: Optional[str] = Field(description="Ex.: apartamento, casa, sala comercial, terreno")
    localizacao: Optional[str] = Field(description="Bairro e/ou cidade citados pelo lead")
    orcamento: Optional[str] = Field(description="Valor ou faixa exatamente como o lead escreveu")

    urgencia: Literal["alta", "media", "baixa"]
    prioridade: int = Field(description="Nota de 1 a 5 seguindo as regras")
    resumo: str = Field(description="Uma frase descrevendo o lead")
    proxima_acao: str = Field(description="Próximo passo sugerido para o corretor")


def ler_leads(caminho):
    """Lê o CSV de leads e devolve uma lista de dicionários, um por linha.

    As chaves de cada dicionário são os nomes das colunas do cabeçalho.
    """
    with open(caminho, encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def qualificar(client, lead):
    """Envia a mensagem de um lead para a API e devolve a qualificação.

    O parse transforma a classe LeadQualificado em esquema JSON, envia junto
    com as instruções e, na volta, converte e valida a resposta.
    """
    resposta = client.messages.parse(
        model=MODELO,
        max_tokens=4096,  # limite de tamanho da resposta, obrigatório na API
        system=INSTRUCOES,
        messages=[{"role": "user", "content": f"Mensagem do lead:\n{lead['mensagem']}"}],
        output_format=LeadQualificado,
    )

    # Objeto LeadQualificado já convertido do JSON e validado pelo parse
    return resposta.parsed_output


def gravar_resultados(caminho, linhas):
    """Grava os leads qualificados em um CSV.

    A ordem das colunas segue os dados originais do lead, depois os campos
    da qualificação e por último a mensagem, para facilitar a conferência.
    """
    colunas = ["id", "nome", "canal"] + list(LeadQualificado.model_fields) + ["mensagem"]
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)


def main():
    """Qualifica todos os leads do arquivo de entrada e grava o resultado."""
    # Carrega a chave do .env e cria o cliente que faz as chamadas à API
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)

    # Lista de leads, cada um dicionário com as colunas do CSV como chaves
    leads = ler_leads(ARQUIVO_ENTRADA)
    resultados = []

    for lead in leads:
        print(f"Qualificando lead {lead['id']} ({lead['nome']})...")

        # Se a chamada falhar para um lead (rede, limite, resposta inválida),
        # mostra o erro e segue para o próximo em vez de parar tudo
        try:
            qualificado = qualificar(client, lead)
        except Exception as erro:
            print(f"  Falhou: {erro}")
            continue

        # Monta uma linha do CSV num dicionário só, juntando os dados do lead
        # com os campos da qualificação. O model_dump() transforma o objeto em
        # dicionário, e o ** copia todos os pares dele pra dentro deste.
        resultados.append({
            "id": lead["id"],
            "nome": lead["nome"],
            "canal": lead["canal"],
            **qualificado.model_dump(),
            "mensagem": lead["mensagem"],
        })

    # Ordena da maior para a menor prioridade
    resultados.sort(key=lambda linha: linha["prioridade"], reverse=True)

    gravar_resultados(ARQUIVO_SAIDA, resultados)
    print(f"\n{len(resultados)} de {len(leads)} leads qualificados. Resultado em {ARQUIVO_SAIDA}.")


if __name__ == "__main__":
    main()