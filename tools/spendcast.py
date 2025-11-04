# import asyncio
import json
import logging
import os
import httpx
import asyncio

from typing import Any, Dict
#from langchain.tools import tool
from langchain.tools import BaseTool


# from dotenv import load_dotenv
# from fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Configuration ---
class GraphDBConfig(BaseModel):
    """Configuration for the GraphDB connection."""

    url: str = Field(..., description="The URL of the GraphDB SPARQL endpoint.")
    username: str = Field(..., description="The username for GraphDB authentication.")
    password: str = Field(..., description="The password for GraphDB authentication.")

class SPARQLInput(BaseModel):
    query: str = Field(..., description="The SPARQL query string to execute.")

def get_config() -> GraphDBConfig:
    """Loads configuration from environment variables."""
    graphdb_url = os.getenv("GRAPHDB_URL")
    graphdb_user = os.getenv("GRAPHDB_USER")
    graphdb_password = os.getenv("GRAPHDB_PASSWORD")

    if not graphdb_url:
        logger.error("GRAPHDB_URL environment variable not set.")
        raise ValueError("GRAPHDB_URL environment variable not set.")
    if not graphdb_user:
        logger.error("GRAPHDB_USER environment variable not set.")
        raise ValueError("GRAPHDB_USER environment variable not set.")
    if not graphdb_password:
        logger.error("GRAPHDB_PASSWORD environment variable not set.")
        raise ValueError("GRAPHDB_PASSWORD environment variable not set.")

    return GraphDBConfig(
        url=graphdb_url, username=graphdb_user, password=graphdb_password
    )


# --- Query Validation ---
def validate_sparql_query(query: str) -> tuple[bool, str]:
    """
    Basic SPARQL query validation.

    :param query: The SPARQL query string to validate
    :return: Tuple of (is_valid, error_message)
    """
    # Check for required prefixes
    required_prefixes = ["pfm:", "ex:"]
    missing_prefixes = []

    for prefix in required_prefixes:
        if prefix not in query:
            missing_prefixes.append(prefix)

    if missing_prefixes:
        return False, f"Missing required prefixes: {', '.join(missing_prefixes)}"

    # Check for basic SPARQL syntax
    if not query.strip().upper().startswith(("SELECT", "ASK", "CONSTRUCT", "DESCRIBE")):
        return False, "Query must start with SELECT, ASK, CONSTRUCT, or DESCRIBE"

    # Check for balanced braces
    if query.count("{") != query.count("}"):
        return False, "Unbalanced braces in SPARQL query"

    # Check for basic WHERE clause
    if "{" not in query or "}" not in query:
        return False, "Missing WHERE clause with braces"

    return True, "Query is valid"


async def _execute_sparql_impl(query: str) -> Dict[str, Any]:
    """
    Internal implementation of SPARQL query execution.

    :param query: The SPARQL query string to execute.
    :return: The JSON result from GraphDB or an error dictionary.
    """
    config = get_config()
    logger.info(f"Executing SPARQL query on {config.url}")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/sparql-results+json",
    }
    data = {"query": query}
    auth = httpx.BasicAuth(config.username, config.password)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.url, headers=headers, data=data, auth=auth, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        logger.error(error_msg)
        return {"error": error_msg}
    except httpx.RequestError as e:
        error_msg = f"An error occurred while connecting to GraphDB: {e}"
        logger.error(error_msg)
        return {"error": error_msg}
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON response from GraphDB.")
        return {"error": "Invalid JSON response from GraphDB."}


class SPARQLTool(BaseTool):
    name: str = "SPARQLTool"
    description: str = """Executes SPARQL queries in a financial data triple store that contains comprehensive bank account, transaction data about the user and information about the purchased items. Detailed information on: bank accounts, parties, payments, payment cards, financial transactions, purchase receipts, products, product categories, and stores where purchases were made by the user during the period from July 1, 2024, to June 30, 2025.

    # FUNCTIONAL PROPERTIES
    - Each card can only have one scheme operator: pfm:cardSchemeOperator a owl:FunctionalProperty .
    - Each card can only be linked to one account: pfm:linkedAccount a owl:FunctionalProperty .
    - Each merchant can only have one category: pfm:merchantCategory a owl:FunctionalProperty .
    - Each transaction can only have one status: pfm:status a owl:FunctionalProperty .
    - Each transaction can only have one type: pfm:transactionType a owl:FunctionalProperty .
    - Each transaction can only have one value date: pfm:valueDate a owl:FunctionalProperty .
    - Each card can only have one number: pfm:cardNumber a owl:FunctionalProperty .
    - Each card can only have one status: pfm:cardStatus a owl:FunctionalProperty .
    - Each card can only have one type: pfm:cardType a owl:FunctionalProperty .
    - Each card can only have one expiry date: pfm:expiryDate a owl:FunctionalProperty .
    - Each product category can only have one CO2 factor: pfm:co2Factor a owl:FunctionalProperty .
    - Each product category can only have one tax class: pfm:taxClass a owl:FunctionalProperty . 
    
    What follows in yaml format is a collection of common questions and the corresponding SPARQL-query. Use the examples to answer the users questions.
    
    # Instructions
     - Do not escape new lines (\n) within SPARQL queries sent to the tool

    ```yaml
    ---
    - question: Show my profile
      sparql: |
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#>
        select ?name ?birthDate ?phoneNumber
        WHERE {
        ?person a pfm:Person ;
        rdfs:label ?name .
        OPTIONAL { ?person pfm:birthDate ?birthDate } .
        OPTIONAL { ?person pfm:hasTelephoneNumber ?phoneNumber } .
        }
    - question: Show all my accounts with name, purpose, account number, currency and initial balance
      sparql: |
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#>
        SELECT ?label ?accountPurpose ?initialBalance ?accNum ?accountCurrency
        WHERE {
        ?account a pfm:Account ;
            pfm:hasAccountPurpose ?accountPurpose ;
            rdfs:label ?label .
            OPTIONAL{ ?account pfm:hasInitialBalance ?initialBalance} .
            OPTIONAL{ ?account pfm:accountNumber ?accNum} .
            OPTIONAL{ ?account pfm:hasCurrency ?accountCurrency}
            OPTIONAL{ ?account pfm:hasCurrency ?accountCurrency}
        }

    - question: Show me the current balance of the account number "1234567890" between 2024-07-01 and 2025-07-01
      sparql: |
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#>
        SELECT (SUM(IF(?transactionType = 'income', ?amount, -?amount)) as ?balance) where {
        ?account pfm:accountNumber "1234567890" .
        ?participantRole pfm:isPlayedBy ?account .
        ?transaction pfm:hasParticipant ?participantRole .

        ?transaction a pfm:FinancialTransaction ;
        pfm:hasMonetaryAmount ?monetaryAmount ;
        pfm:hasTransactionDate ?transactionDate ;
        pfm:transactionType ?transactionType ;
        pfm:status ?transactionStatus .
            
        ?monetaryAmount pfm:hasCurrency ?currency ;
        pfm:hasAmount ?amount .
            
        FILTER(strstarts(?transactionStatus, "settled"))
        FILTER (?transactionDate >= "2024-07-01"^^xsd:date)
        FILTER (?transactionDate < "2025-07-01"^^xsd:date)
        }
    - question: Show me the last 100 expense transactions ordered by transaction date, descending
      sparql: |
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#>
        SELECT ?transactionId ?transactionDate ?transactionStatus ?transactionType ?amount ?currency ?payer ?payee ?receiptId {
            ?transaction a pfm:FinancialTransaction ;
            pfm:hasMonetaryAmount ?monetaryAmount ;
            pfm:hasTransactionDate ?transactionDate ;
            pfm:transactionType ?transactionType ;    
            rdfs:label ?transactionId ;
            pfm:status ?transactionStatus ;
            pfm:hasParticipant [
                a pfm:Payer ;
                pfm:isPlayedBy/rdfs:label ?payer
            #pfm:accountNumber ?payerAccountNumber 
            ] ;
            pfm:hasParticipant [
                a pfm:Payee ;
                pfm:isPlayedBy/rdfs:label ?payee 
            ] .
        
            OPTIONAL { ?transaction pfm:hasReceipt/rdfs:label ?receiptId } .
            ?monetaryAmount pfm:hasCurrency ?currency ;
            pfm:hasAmount ?amount .
        }

    - question: Show me all my payment cards
      sparql: |
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#> 
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
        SELECT ?cardNumber ?cardType ?expiryDate ?linkedAccountNumber ?cardIssuer ?cardSchemeOperator WHERE { 
            ?card a pfm:PaymentCard ;
            pfm:cardNumber ?cardNumber ;
            pfm:cardType ?cardType ;
            pfm:expiryDate ?expiryDate ;
            pfm:hasCardIssuer/pfm:isPlayedBy/rdfs:label ?cardIssuer ;
            pfm:cardSchemeOperator/pfm:isPlayedBy/rdfs:label ?cardSchemeOperator ;
            pfm:linkedAccount/pfm:accountNumber ?linkedAccountNumber .
        }
    - question: Show me the transactions of the payment card number "4731042107549834" from 2024-07-01 to 2025-07-01
      sparql: |
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#> 
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> 
        SELECT ?transactionId ?transactionDate ?transactionType ?transactionStatus ?amount ?currency ?recieptId WHERE { 
            ?card pfm:cardNumber "4731042107549834" .
            ?transaction a pfm:FinancialTransaction ;
            rdfs:label ?transactionId ;
            pfm:hasCard ?card ;
            pfm:hasMonetaryAmount ?monetaryAmount ;
            pfm:hasTransactionDate ?transactionDate ;
            pfm:transactionType ?transactionType ;
            pfm:status ?transactionStatus .
            OPTIONAL { ?transaction pfm:hasReceipt/rdfs:label ?recieptId }.

            ?monetaryAmount pfm:hasCurrency ?currency .
            ?monetaryAmount pfm:hasAmount ?amount .
            
            FILTER(strstarts(?transactionStatus, "settled"))
            FILTER (?transactionDate >= "2024-07-01"^^xsd:date)
            FILTER (?transactionDate < "2025-07-01"^^xsd:date)
        }

    - question: Show me all merchants that received a payment between 2024-10-01 and 2024-10-31
      sparql: |
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#>
        SELECT DISTINCT ?payee WHERE {
            ?transaction a pfm:FinancialTransaction ;
            pfm:hasTransactionDate ?transactionDate ;
            pfm:transactionType ?transactionType ;    
            pfm:hasParticipant [
                a pfm:Payee ;
                pfm:isPlayedBy/rdfs:label ?payee 
            ] .

            FILTER(strstarts(?transactionType, "expense"))
            FILTER (?transactionDate >= "2024-10-01"^^xsd:date)
            FILTER (?transactionDate < "2024-10-31"^^xsd:date)
        }  

    - question: Show me the receipt with the id="Receipt 20250627_184626_0033091_251_260"
      sparql: |
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#>
        SELECT ?receiptId ?receiptDate ?totalAmount ?currency ?cardNumber 
        WHERE {
        ?receipt a pfm:Receipt ;
            rdfs:label "Receipt 20250627_184626_0033091_251_260" ;
            pfm:hasCard/pfm:cardNumber ?cardNumber ;
            pfm:receiptDate ?receiptDate ;
            pfm:receiptId ?receiptId ;
            pfm:hasTotalAmount [a pfm:MonetaryAmount ; pfm:hasAmount ?totalAmount; pfm:hasCurrency ?currency] .
        }
    - question: Show me the line items of the receipt with the id="Receipt 20250627_184626_0033091_251_260"
      sparql: |
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX pfm: <https://static.rwpz.net/spendcast/schema#>
        SELECT ?description ?quantity ?unitPrice ?lineSubtotal ?productUrls
        WHERE {
            #?account a pfm:Account ;
            #pfm:hasAccountPurpose ?accountPurpose ;
            ?receipt a pfm:Receipt ;
                    rdfs:label "Receipt 20250627_184626_0033091_251_260";
        pfm:hasLineItem	?lineItem .
        ?lineItem pfm:itemDescription ?description ;
            pfm:quantity ?quantity ;
            pfm:unitPrice ?unitPrice ;
                pfm:lineSubtotal ?lineSubtotal ;
            pfm:hasProduct [a pfm:Product ; 
            pfm:productUrls ?productUrls ;
                pfm:category [a pfm:ProductCategory ; rdfs:label ?category ]] .
        }
    ```
    """

    # args_schema: Type[BaseModel] = SPARQLInput 
    # description = """
    # Executes SPARQL queries in a financial data triple store that contains comprehensive bank account, transaction, and retail data for the user. \n\n

    # **Core Financial Entities:**\n
    # - **Accounts**: Checking, savings, credit cards, retirement accounts (3A pillar)\n
    # - **Parties**: People (customers) and organizations (banks, merchants) with detailed contact information\n
    # - **Payment Cards**: Credit/debit cards linked to accounts for transactions\n
    # - **Financial Transactions**: Complete transaction records with amounts, dates, status, and types\n\n
    # **Retail & Receipt Data:**\n
    # - **Receipts**: Detailed purchase receipts with line items, dates, and payment methods\n
    # - **Products**: Migros product catalog with EAN codes, names, and category links\n
    # - **Product Categories**: Hierarchical classification (beverages, bread, cleaning, etc.)\n
    # - **Merchants**: Business entities with names and addresses\n\n
    # **Key Data Properties:**\n
    # - Transaction amounts in CHF with currency information\n
    # - Complete transaction dates and status tracking\n
    # - Account balances and payment card details\n
    # - Product information and receipt line items\n
    # - Customer account and card relationships\n\n
    # **Query Capabilities:**\n
    # - Find transactions by customer, date, amount, or merchant\n
    # - Analyze spending patterns through accounts and payment cards\n
    # - Track account balances and payment card usage\n
    # - Search products and receipt details\n
    # - Analyze customer financial relationships\n\n
    # **Important Data Structure Insights:**\n
    # - **Customers** are `pfm:Person` entities with direct `pfm:hasAccount` relationships\n
    # - **Payment Cards** are linked to accounts via `pfm:linkedAccount`\n
    # - **Transactions** use accounts (not cards directly) through `pfm:hasParticipant` + `pfm:Payer` role + `pfm:isPlayedBy`\n
    # - **Product Categories** now work correctly with proper `pfm:category` relationships and hierarchical structure\n
    # - **Party Roles** (Payer, Payee, AccountHolder, CardHolder) mediate relationships between entities\n\n
    # **Common Query Patterns:**\n
    # - Use `pfm:` prefix for schema properties (e.g., `pfm:hasMonetaryAmount`)\n
    # - Use `ex:` prefix for data instances (e.g., `ex:Swiss_franc`)\n
    # - Find customer transactions through accounts: `?person pfm:hasAccount ?account`\n
    # - Find card transactions through linked accounts: `?card pfm:linkedAccount ?account`\n
    # - Join transactions with receipts using `pfm:hasReceipt`

    # :param ctx: The tool context (unused in this implementation).
    # :param query: The SPARQL query string to execute.
    # :return: The JSON result from GraphDB or an error dictionary.
    # """

    # Optional: define JSON schema for arguments
    args_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The SPARQL query string to execute",
            }
        },
        "required": ["query"],
    }

    def _run(self, query: str) -> Dict[str, Any]:
        return asyncio.run(_execute_sparql_impl(query))

    async def _arun(self, query: str) -> Dict[str, Any]:
        logger.info(f"SPARQL tool, got query: {query}")
        return await _execute_sparql_impl(query)



"""
    **IMPORTANT: Before writing queries, use these tools for schema help:**
    - `get_schema_help()` - Complete schema information and examples (recommended)
    - `get_schema_content('schema_summary')` - Read entity relationships and schema patterns
    - `get_schema_content('example_queries')` - Read working SPARQL examples

    ** Pro Tip:** Use `get_schema_help()` to get complete schema information and examples before writing queries!\n\n
    **Example Queries:**\n
    - Find all transactions for a specific customer\n
    - Find transactions through bank accounts only\n
    - Find transactions through payment cards only\n
    - Get customer account summary\n
    - Monthly spending by category\n
    - Top spending merchants\n
    - Payment card usage patterns\n
"""
