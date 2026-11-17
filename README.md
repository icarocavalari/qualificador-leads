# Qualificador de leads imobiliários com IA

Script em Python que lê as primeiras mensagens de leads de uma imobiliária, usa a API do Claude para extrair o que cada pessoa procura e gera uma lista priorizada pronta para o time comercial e para o CRM.

## O problema

Uma imobiliária recebe mensagens de vários canais ao mesmo tempo (WhatsApp, site, Instagram, portais). Algumas são de clientes prontos para fechar, outras são vagas, de parceiros ou simplesmente spam. Quando tudo chega misturado, o corretor perde tempo com quem não vai comprar e demora para responder quem está com pressa.

Este projeto faz a triagem inicial automaticamente. Para cada mensagem ele identifica o tipo de contato, a operação, o imóvel, a localização, o orçamento e a urgência, atribui uma prioridade de 1 a 5 e sugere a próxima ação do corretor.

## Exemplo

Mensagem recebida pelo WhatsApp

> apto 3 dorms moema ate 1.2mi urgente!!! transferido de cidade, começo no trampo novo dia 1

Resultado gerado

| Campo | Valor |
|---|---|
| tipo_contato | comprador |
| operacao | compra |
| tipo_imovel | apartamento |
| localizacao | Moema |
| orcamento | ate 1.2mi |
| urgencia | alta |
| prioridade | 5 |
| proxima_acao | Ligar hoje para o lead, confirmar a data de mudança e enviar uma seleção de apartamentos de 3 dormitórios em Moema até 1.2mi. |

O resultado completo dos 20 leads de teste está em [`resultados.csv`](resultados.csv).

## Como a prioridade é definida

As regras são avaliadas de cima para baixo e vale a primeira que se aplicar.

| Prioridade | Quando |
|---|---|
| 1 | Não é cliente (spam, parceiro comercial, elogio ou comentário sem pedido) |
| 5 | Lead que já está em atendimento e reclama de falta de retorno |
| 5 | Sabe se quer comprar ou alugar, informou orçamento e tem urgência alta |
| 4 | Sabe se quer comprar, alugar ou vender, mas falta orçamento ou a urgência não é alta |
| 3 | Interesse real, mas ainda não sabe se compra ou aluga |
| 2 | Mensagem vaga demais para saber o que a pessoa quer |

## Decisões de projeto

**Resposta em formato fixo.** O script usa o recurso de structured outputs da API junto com um modelo Pydantic (`LeadQualificado`). A API garante que a resposta segue o esquema e o Pydantic valida cada campo antes de gravar. Campos de categoria, como urgência e tipo de contato, só aceitam valores de uma lista fechada.

**Nunca inventar dados.** Quando a mensagem não informa algo, o campo fica vazio em vez de receber um palpite. O orçamento é copiado do jeito que o lead escreveu, sem conversão.

**Deduzir não é inventar.** Um orçamento de "até 600 mil" indica compra mesmo sem a palavra "comprar", e um valor por mês indica aluguel. Essa dedução está explícita nas regras, porque sem ela os leads mais quentes acabavam marcados como indefinidos.

**Lead em atendimento sem retorno é prioridade máxima.** Uma pessoa que já falou com um corretor e ficou sem resposta é o lead com maior risco de ser perdido, mesmo sem informar orçamento.

**Falha isolada por lead.** Se a chamada falhar para uma mensagem (rede, limite de tokens, resposta inválida), o erro é mostrado e o script segue para a próxima, sem perder o processamento das outras.

**Limite de tokens com folga.** O `max_tokens` considera também o raciocínio interno do modelo. Com um limite baixo, algumas respostas eram cortadas no meio do JSON.

## Como foi avaliado

Os 20 leads de teste em [`leads.csv`](leads.csv) são fictícios e foram montados para cobrir casos difíceis, como mensagens vagas ("vcs tem algo"), escrita informal, lead em inglês, spam, corretor oferecendo parceria, proprietário querendo vender e cliente reclamando de falta de retorno.

A cada rodada eu conferi os casos de erro e ajustei as regras. Um aprendizado foi que cada regra nova muda a forma como o modelo lê as outras. Deixar a regra de "não inventar" mais rígida, por exemplo, fez leads com orçamento de compra serem marcados como indefinidos, o que levou à regra de dedução pelo orçamento.

## Limitações e próximos passos

- O modelo pode variar um pouco entre execuções, principalmente em casos de fronteira entre duas prioridades.
- O próximo passo seria o modelo apenas extrair os fatos (operação, orçamento, urgência, se já está em atendimento) e o cálculo da prioridade ficar em Python. Assim a regra de negócio fica determinística, testável e fácil de mudar.
- Receber os leads por webhook, a partir de um formulário ou do WhatsApp, em vez de um arquivo CSV.
- Gravar o resultado direto no CRM (por exemplo HubSpot) via API.

## Como rodar

Pré-requisitos são Python 3 e uma chave da [API do Claude](https://platform.claude.com).

```bash
git clone https://github.com/icarocavalari/qualificador-leads.git
cd qualificador-leads

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz do projeto com a sua chave

```
ANTHROPIC_API_KEY=sua-chave-aqui
```

E rode

```bash
python qualificar_leads.py
```

O resultado é gravado em `resultados.csv`, ordenado da maior para a menor prioridade.

## Tecnologias

Python, API do Claude (modelo Claude Haiku), Pydantic e python-dotenv.