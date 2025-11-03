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
    description: str = """Executes SPARQL queries in a financial data triple store that contains comprehensive bank account, transaction, and retail data about the user. Detailed information on: bank accounts, parties, payments, payment cards, financial transactions, purchase receipts, products, product categories, and stores where purchases were made by the user during the period from July 1, 2024, to June 30, 2025.
    
    Schema of the RDF Graph:
    https://static.rwpz.net/spendcast/schema#

    @prefix pfm: <https://static.rwpz.net/spendcast/schema#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .

    # Ontology Declaration
    pfm: a owl:Ontology ;
        rdfs:label "FIBO Demo Extension Ontology" ;
        rdfs:comment "Self-contained extension ontology for the FIBO demo financial data model" ;
        owl:versionInfo "2.0" .

    # =============================================================================
    # CLASS DEFINITIONS
    # =============================================================================

    # Account Class
    pfm:Account a owl:Class ;
        rdfs:label "Account" ;
        rdfs:comment "Container for records associated with a business arrangement for regular transactions and services" .

    # Checking Account Class
    pfm:CheckingAccount a owl:Class ;
        rdfs:label "Checking Account" ;
        rdfs:comment "A type of account that allows for frequent deposits and withdrawals" ;
        rdfs:subClassOf pfm:Account .

    # Savings Account Class
    pfm:SavingsAccount a owl:Class ;
        rdfs:label "Savings Account" ;
        rdfs:comment "A type of account designed for saving money with interest" ;
        rdfs:subClassOf pfm:Account .

    # Credit Card Account Class
    pfm:CreditCard a owl:Class ;
        rdfs:label "Credit Card Account" ;
        rdfs:comment "A type of account for credit card transactions" ;
        rdfs:subClassOf pfm:Account .

    # Retirement Account 3A Class
    pfm:Retirement3A a owl:Class ;
        rdfs:label "Retirement Account 3A" ;
        rdfs:comment "A Swiss third pillar retirement account" ;
        rdfs:subClassOf pfm:Account .

    # Other Account Class
    pfm:Other a owl:Class ;
        rdfs:label "Other Account" ;
        rdfs:comment "Other types of accounts not specifically categorized" ;
        rdfs:subClassOf pfm:Account .

    # Party Class
    pfm:Party a owl:Class ;
        rdfs:label "Party" ;
        rdfs:comment "An entity that can participate in financial transactions" .

    # Organization Class
    pfm:Organization a owl:Class ;
        rdfs:label "Organization" ;
        rdfs:comment "A structured group of people with a common purpose" ;
        rdfs:subClassOf pfm:Party .

    # Person Class
    pfm:Person a owl:Class ;
        rdfs:label "Person" ;
        rdfs:comment "An individual human being" ;
        rdfs:subClassOf pfm:Party .

    # Merchant Class
    pfm:Merchant a owl:Class ;
        rdfs:label "Merchant" ;
        rdfs:comment "An organization that sells goods or services" ;
        rdfs:subClassOf pfm:Organization .

    # Bank Class
    pfm:Bank a owl:Class ;
        rdfs:label "Bank" ;
        rdfs:comment "A financial institution that provides banking services" ;
        rdfs:subClassOf pfm:Organization .

    # Payment Card Class
    pfm:PaymentCard a owl:Class ;
        rdfs:label "Payment Card" ;
        rdfs:comment "A card used for making payments" .

    # Financial Transaction Class
    pfm:FinancialTransaction a owl:Class ;
        rdfs:label "Financial Transaction" ;
        rdfs:comment "A financial event involving the transfer of money" .

    # Monetary Amount Class
    pfm:MonetaryAmount a owl:Class ;
        rdfs:label "Monetary Amount" ;
        rdfs:comment "An amount of money with a specified currency" .

    # Party Role Class
    pfm:PartyRole a owl:Class ;
        rdfs:label "Party Role" ;
        rdfs:comment "A role that a party can play in a financial context" .

    # Payer Class
    pfm:Payer a owl:Class ;
        rdfs:label "Payer" ;
        rdfs:comment "A party that pays money in a transaction" ;
        rdfs:subClassOf pfm:PartyRole .

    # Payee Class
    pfm:Payee a owl:Class ;
        rdfs:label "Payee" ;
        rdfs:comment "A party that receives money in a transaction" ;
        rdfs:subClassOf pfm:PartyRole .

    # Account Holder Class
    pfm:AccountHolder a owl:Class ;
        rdfs:label "Account Holder" ;
        rdfs:comment "A party that owns an account" ;
        rdfs:subClassOf pfm:PartyRole .

    # Account Provider Class
    pfm:AccountProvider a owl:Class ;
        rdfs:label "Account Provider" ;
        rdfs:comment "A party that provides and services an account" ;
        rdfs:subClassOf pfm:PartyRole .

    # Card Issuer Class
    pfm:CardIssuer a owl:Class ;
        rdfs:label "Card Issuer" ;
        rdfs:comment "A party that issues payment cards" ;
        rdfs:subClassOf pfm:PartyRole .

    # Card Holder Class
    pfm:CardHolder a owl:Class ;
        rdfs:label "Card Holder" ;
        rdfs:comment "A party that holds a payment card" ;
        rdfs:subClassOf pfm:PartyRole .

    # Currency Class
    pfm:Currency a owl:Class ;
        rdfs:label "Currency" ;
        rdfs:comment "A medium of exchange value" .

    # Product Category Class
    pfm:ProductCategory a owl:Class ;
        rdfs:label "Product Category" ;
        rdfs:comment "A category for classifying products and services" ;
        rdfs:subClassOf owl:Thing .

    # Product Class
    pfm:Product a owl:Class ;
        rdfs:label "Product" ;
        rdfs:comment "A good or service that can be purchased" .

    # Receipt Class
    pfm:Receipt a owl:Class ;
        rdfs:label "Receipt" ;
        rdfs:comment "A document confirming a purchase transaction" .

    # Receipt Line Item Class
    pfm:ReceiptLineItem a owl:Class ;
        rdfs:label "Receipt Line Item" ;
        rdfs:comment "An individual item on a receipt" .

    # Currency Conversion Class
    pfm:CurrencyConversion a owl:Class ;
        rdfs:label "Currency Conversion" ;
        rdfs:comment "A conversion between different currencies" .

    # Card Scheme Operator Class
    pfm:CardSchemeOperator a owl:Class ;
        rdfs:label "Card Scheme Operator" ;
        rdfs:comment "An organization that operates a payment card scheme" ;
        rdfs:subClassOf pfm:Organization .

    # =============================================================================
    # OBJECT PROPERTIES
    # =============================================================================

    # Account Holder Property
    pfm:hasAccountHolder a owl:ObjectProperty ;
        rdfs:label "has account holder" ;
        rdfs:comment "Links an account to its holder" ;
        rdfs:domain pfm:Account ;
        rdfs:range pfm:AccountHolder .

    # Account Provider Property
    pfm:hasAccountProvider a owl:ObjectProperty ;
        rdfs:label "has account provider" ;
        rdfs:comment "Links an account to its provider" ;
        rdfs:domain pfm:Account ;
        rdfs:range pfm:AccountProvider .

    # Card Issuer Property
    pfm:hasCardIssuer a owl:ObjectProperty ;
        rdfs:label "has card issuer" ;
        rdfs:comment "Links a payment card to its issuer" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range pfm:CardIssuer .

    # Card Holder Property
    pfm:hasCardHolder a owl:ObjectProperty ;
        rdfs:label "has card holder" ;
        rdfs:comment "Links a payment card to its holder" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range pfm:CardHolder .

    # Card Scheme Operator Property
    pfm:cardSchemeOperator a owl:ObjectProperty ;
        rdfs:label "card scheme operator" ;
        rdfs:comment "Links a payment card to its scheme operator" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range pfm:CardSchemeOperator .

    # Linked Account Property
    pfm:linkedAccount a owl:ObjectProperty ;
        rdfs:label "linked account" ;
        rdfs:comment "Links a payment card to its associated account" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range pfm:Account .

    # Merchant Category Property
    pfm:merchantCategory a owl:ObjectProperty ;
        rdfs:label "merchant category" ;
        rdfs:comment "Links a merchant to their category classification" ;
        rdfs:domain pfm:Organization ;
        rdfs:range skos:Concept .

    # Has Account Property
    pfm:hasAccount a owl:ObjectProperty ;
        rdfs:label "has account" ;
        rdfs:comment "Links a party to their accounts" ;
        rdfs:domain pfm:Party ;
        rdfs:range pfm:Account .

    # Has Participant Property
    pfm:hasParticipant a owl:ObjectProperty ;
        rdfs:label "has participant" ;
        rdfs:comment "Links a transaction to its participants" ;
        rdfs:domain pfm:FinancialTransaction ;
        rdfs:range pfm:PartyRole .

    # Has Monetary Amount Property
    pfm:hasMonetaryAmount a owl:ObjectProperty ;
        rdfs:label "has monetary amount" ;
        rdfs:comment "Links a transaction to its monetary amount" ;
        rdfs:domain pfm:FinancialTransaction ;
        rdfs:range pfm:MonetaryAmount .

    # Has Currency Property
    pfm:hasCurrency a owl:ObjectProperty ;
        rdfs:label "has currency" ;
        rdfs:comment "Links a monetary amount to its currency" ;
        rdfs:domain pfm:MonetaryAmount ;
        rdfs:range pfm:Currency .

    # Has Amount Property
    pfm:hasAmount a owl:ObjectProperty ;
        rdfs:label "has amount" ;
        rdfs:comment "Links a monetary amount to its numeric value" ;
        rdfs:domain pfm:MonetaryAmount .

    # Has Transaction Date Property
    pfm:hasTransactionDate a owl:ObjectProperty ;
        rdfs:label "has transaction date" ;
        rdfs:comment "Links a transaction to its date" ;
        rdfs:domain pfm:FinancialTransaction .

    # Is Played By Property
    pfm:isPlayedBy a owl:ObjectProperty ;
        rdfs:label "is played by" ;
        rdfs:comment "Links a role to the party that plays it" ;
        rdfs:domain pfm:PartyRole ;
        rdfs:range pfm:Party .

    # Has Receipt Property
    pfm:hasReceipt a owl:ObjectProperty ;
        rdfs:label "has receipt" ;
        rdfs:comment "Links a transaction to its receipt" ;
        rdfs:domain pfm:FinancialTransaction ;
        rdfs:range pfm:Receipt .

    # Has Line Item Property
    pfm:hasLineItem a owl:ObjectProperty ;
        rdfs:label "has line item" ;
        rdfs:comment "Links a receipt to its line items" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range pfm:ReceiptLineItem .

    # Has Product Property
    pfm:hasProduct a owl:ObjectProperty ;
        rdfs:label "has product" ;
        rdfs:comment "Links a line item to its product" ;
        rdfs:domain pfm:ReceiptLineItem ;
        rdfs:range pfm:Product .

    # Has Category Property
    pfm:hasCategory a owl:ObjectProperty ;
        rdfs:label "has category" ;
        rdfs:comment "Links a product to its category" ;
        rdfs:domain pfm:Product ;
        rdfs:range pfm:ProductCategory .

    # Has Parent Category Property
    pfm:hasParentCategory a owl:ObjectProperty ;
        rdfs:label "has parent category" ;
        rdfs:comment "Links a category to its parent category" ;
        rdfs:domain pfm:ProductCategory ;
        rdfs:range pfm:ProductCategory .

    # Has Currency Conversion Property
    pfm:hasCurrencyConversion a owl:ObjectProperty ;
        rdfs:label "has currency conversion" ;
        rdfs:comment "Links a transaction to its currency conversion" ;
        rdfs:domain pfm:FinancialTransaction ;
        rdfs:range pfm:CurrencyConversion .

    # Has Base Amount Property
    pfm:hasBaseAmount a owl:ObjectProperty ;
        rdfs:label "has base amount" ;
        rdfs:comment "Links a currency conversion to its base amount" ;
        rdfs:domain pfm:CurrencyConversion ;
        rdfs:range pfm:MonetaryAmount .

    # Has Counter Amount Property
    pfm:hasCounterAmount a owl:ObjectProperty ;
        rdfs:label "has counter amount" ;
        rdfs:comment "Links a currency conversion to its counter amount" ;
        rdfs:domain pfm:CurrencyConversion ;
        rdfs:range pfm:MonetaryAmount .

    # Has Card Property
    pfm:hasCard a owl:ObjectProperty ;
        rdfs:label "has card" ;
        rdfs:comment "Links a transaction or receipt to its payment card" ;
        rdfs:range pfm:PaymentCard .

    # Has Total Amount Property
    pfm:hasTotalAmount a owl:ObjectProperty ;
        rdfs:label "has total amount" ;
        rdfs:comment "Links a receipt to its total amount" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range pfm:MonetaryAmount .

    # =============================================================================
    # DATA PROPERTIES
    # =============================================================================

    # Account Number Property
    pfm:accountNumber a owl:DatatypeProperty ;
        rdfs:label "account number" ;
        rdfs:comment "The account number identifier" ;
        rdfs:domain pfm:Account ;
        rdfs:range xsd:string .

    # International Bank Account Identifier Property
    pfm:hasInternationalBankAccountIdentifier a owl:DatatypeProperty ;
        rdfs:label "has international bank account identifier" ;
        rdfs:comment "The IBAN (International Bank Account Number)" ;
        rdfs:domain pfm:Account ;
        rdfs:range xsd:string .

    # Account Purpose Property
    pfm:hasAccountPurpose a owl:DatatypeProperty ;
        rdfs:label "has account purpose" ;
        rdfs:comment "The purpose of the account" ;
        rdfs:domain pfm:Account ;
        rdfs:range xsd:string .

    # Initial Balance Property
    pfm:hasInitialBalance a owl:DatatypeProperty ;
        rdfs:label "has initial balance" ;
        rdfs:comment "The initial balance of the account" ;
        rdfs:domain pfm:Account ;
        rdfs:range xsd:decimal .

    # Overdraft Limit Property
    pfm:hasOverdraftLimit a owl:DatatypeProperty ;
        rdfs:label "has overdraft limit" ;
        rdfs:comment "The overdraft limit of the account" ;
        rdfs:domain pfm:Account ;
        rdfs:range xsd:decimal .

    # Has Name Property
    pfm:hasName a owl:DatatypeProperty ;
        rdfs:label "has name" ;
        rdfs:comment "The name of a party" ;
        rdfs:domain pfm:Party ;
        rdfs:range xsd:string .

    # Has Telephone Number Property
    pfm:hasTelephoneNumber a owl:DatatypeProperty ;
        rdfs:label "has telephone number" ;
        rdfs:comment "The telephone number of a party" ;
        rdfs:domain pfm:Party ;
        rdfs:range xsd:string .

    # Has Email Address Property
    pfm:hasEmailAddress a owl:DatatypeProperty ;
        rdfs:label "has email address" ;
        rdfs:comment "The email address of a party" ;
        rdfs:domain pfm:Party ;
        rdfs:range xsd:string .

    # Birth Date Property
    pfm:birthDate a owl:DatatypeProperty ;
        rdfs:label "birth date" ;
        rdfs:comment "The birth date of a person" ;
        rdfs:domain pfm:Person ;
        rdfs:range xsd:date .

    # Address Class
    pfm:Address a owl:Class ;
        rdfs:label "Address" ;
        rdfs:comment "A physical or logical address" .

    # Has Address Property
    pfm:hasAddress a owl:ObjectProperty ;
        rdfs:label "has address" ;
        rdfs:comment "Links a party to an address" ;
        rdfs:domain pfm:Party ;
        rdfs:range pfm:Address .

    # Address Type Property
    pfm:addressType a owl:DatatypeProperty ;
        rdfs:label "address type" ;
        rdfs:comment "The type of address (e.g., home, work, billing)" ;
        rdfs:domain pfm:Address ;
        rdfs:range xsd:string .

    # Street Property
    pfm:street a owl:DatatypeProperty ;
        rdfs:label "street" ;
        rdfs:comment "The street address" ;
        rdfs:domain pfm:Address ;
        rdfs:range xsd:string .

    # City Property
    pfm:city a owl:DatatypeProperty ;
        rdfs:label "city" ;
        rdfs:comment "The city name" ;
        rdfs:domain pfm:Address ;
        rdfs:range xsd:string .

    # Postal Code Property
    pfm:postalCode a owl:DatatypeProperty ;
        rdfs:label "postal code" ;
        rdfs:comment "The postal or ZIP code" ;
        rdfs:domain pfm:Address ;
        rdfs:range xsd:string .

    # Country Property
    pfm:country a owl:DatatypeProperty ;
        rdfs:label "country" ;
        rdfs:comment "The country name" ;
        rdfs:domain pfm:Address ;
        rdfs:range xsd:string .

    # State Property
    pfm:state a owl:DatatypeProperty ;
        rdfs:label "state" ;
        rdfs:comment "The state or province name" ;
        rdfs:domain pfm:Address ;
        rdfs:range xsd:string .

    # Description Property
    pfm:description a owl:DatatypeProperty ;
        rdfs:label "description" ;
        rdfs:comment "A description of the address" ;
        rdfs:domain pfm:Address ;
        rdfs:range xsd:string .

    # Legacy Address Property (for backward compatibility)
    pfm:address a owl:DatatypeProperty ;
        rdfs:label "address" ;
        rdfs:comment "The address of a party (legacy format)" ;
        rdfs:domain pfm:Party ;
        rdfs:range xsd:string .

    # Citizenship Property
    pfm:citizenship a owl:DatatypeProperty ;
        rdfs:label "citizenship" ;
        rdfs:comment "The citizenship of a person" ;
        rdfs:domain pfm:Person ;
        rdfs:range xsd:string .

    # Transaction Status Property
    pfm:status a owl:DatatypeProperty ;
        rdfs:label "transaction status" ;
        rdfs:comment "The status of a financial transaction" ;
        rdfs:domain pfm:FinancialTransaction ;
        rdfs:range xsd:string .

    # Transaction Type Property
    pfm:transactionType a owl:DatatypeProperty ;
        rdfs:label "transaction type" ;
        rdfs:comment "The type of financial transaction (e.g., expense, income)" ;
        rdfs:domain pfm:FinancialTransaction ;
        rdfs:range xsd:string .

    # Value Date Property
    pfm:valueDate a owl:DatatypeProperty ;
        rdfs:label "value date" ;
        rdfs:comment "The value date of a financial transaction" ;
        rdfs:domain pfm:FinancialTransaction ;
        rdfs:range xsd:date .

    # Card Number Property
    pfm:cardNumber a owl:DatatypeProperty ;
        rdfs:label "card number" ;
        rdfs:comment "The card number of a payment card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:string .

    # Card Status Property
    pfm:cardStatus a owl:DatatypeProperty ;
        rdfs:label "card status" ;
        rdfs:comment "The status of a payment card (e.g., active, inactive)" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:string .

    # Card Type Property
    pfm:cardType a owl:DatatypeProperty ;
        rdfs:label "card type" ;
        rdfs:comment "The type of payment card (e.g., debit, credit)" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:string .

    # Contactless Enabled Property
    pfm:contactlessEnabled a owl:DatatypeProperty ;
        rdfs:label "contactless enabled" ;
        rdfs:comment "Whether contactless payments are enabled for the card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:boolean .

    # Daily Limit Property
    pfm:dailyLimit a owl:DatatypeProperty ;
        rdfs:label "daily limit" ;
        rdfs:comment "The daily spending limit for a payment card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:decimal .

    # Expiry Date Property
    pfm:expiryDate a owl:DatatypeProperty ;
        rdfs:label "expiry date" ;
        rdfs:comment "The expiry date of a payment card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:string .

    # International Enabled Property
    pfm:internationalEnabled a owl:DatatypeProperty ;
        rdfs:label "international enabled" ;
        rdfs:comment "Whether international transactions are enabled for the card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:boolean .

    # Monthly Limit Property
    pfm:monthlyLimit a owl:DatatypeProperty ;
        rdfs:label "monthly limit" ;
        rdfs:comment "The monthly spending limit for a payment card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:decimal .

    # Online Enabled Property
    pfm:onlineEnabled a owl:DatatypeProperty ;
        rdfs:label "online enabled" ;
        rdfs:comment "Whether online transactions are enabled for the card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:boolean .

    # Withdrawal Enabled Property
    pfm:withdrawalEnabled a owl:DatatypeProperty ;
        rdfs:label "withdrawal enabled" ;
        rdfs:comment "Whether cash withdrawals are enabled for the card" ;
        rdfs:domain pfm:PaymentCard ;
        rdfs:range xsd:boolean .

    # Tax Class Property
    pfm:taxClass a owl:DatatypeProperty ;
        rdfs:label "tax class" ;
        rdfs:comment "The tax classification for a product category" ;
        rdfs:domain pfm:ProductCategory ;
        rdfs:range xsd:string .

    # Short Name Property
    pfm:shortName a owl:DatatypeProperty ;
        rdfs:label "short name" ;
        rdfs:comment "A short name for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # EAN Property
    pfm:ean a owl:DatatypeProperty ;
        rdfs:label "EAN" ;
        rdfs:comment "The European Article Number (barcode)" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Unit Price Property
    pfm:unitPrice a owl:DatatypeProperty ;
        rdfs:label "unit price" ;
        rdfs:comment "The unit price of a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:decimal .

    # Tax Rate Property
    pfm:taxRate a owl:DatatypeProperty ;
        rdfs:label "tax rate" ;
        rdfs:comment "The tax rate for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:decimal .

    # SKU Property
    pfm:sku a owl:DatatypeProperty ;
        rdfs:label "SKU" ;
        rdfs:comment "The Stock Keeping Unit identifier" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Origin Property
    pfm:origin a owl:DatatypeProperty ;
        rdfs:label "origin" ;
        rdfs:comment "The origin of a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Packaging Size Property
    pfm:packagingSize a owl:DatatypeProperty ;
        rdfs:label "packaging size" ;
        rdfs:comment "The packaging size of a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # CO2 Production Property
    pfm:co2Production a owl:DatatypeProperty ;
        rdfs:label "CO2 production" ;
        rdfs:comment "The CO2 production for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:decimal .

    # CO2 Transportation Property
    pfm:co2Transportation a owl:DatatypeProperty ;
        rdfs:label "CO2 transportation" ;
        rdfs:comment "The CO2 transportation for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:decimal .

    # CO2 Packaging Property
    pfm:co2Packaging a owl:DatatypeProperty ;
        rdfs:label "CO2 packaging" ;
        rdfs:comment "The CO2 packaging for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:decimal .

    # Migros ID Property
    pfm:migrosId a owl:DatatypeProperty ;
        rdfs:label "Migros ID" ;
        rdfs:comment "The Migros internal product identifier" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros Online ID Property
    pfm:migrosOnlineId a owl:DatatypeProperty ;
        rdfs:label "Migros Online ID" ;
        rdfs:comment "The Migros online product identifier" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros Name Property
    pfm:name a owl:DatatypeProperty ;
        rdfs:label "name" ;
        rdfs:comment "The name of a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros UID Property
    pfm:uid a owl:DatatypeProperty ;
        rdfs:label "UID" ;
        rdfs:comment "The unique identifier for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros Description Property
    pfm:description a owl:DatatypeProperty ;
        rdfs:label "description" ;
        rdfs:comment "The description of a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros Origin Property
    pfm:origin a owl:DatatypeProperty ;
        rdfs:label "origin" ;
        rdfs:comment "The origin of a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros Migipedia URL Property
    pfm:migipediaUrl a owl:DatatypeProperty ;
        rdfs:label "Migipedia URL" ;
        rdfs:comment "The Migipedia URL for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Image URL Property
    pfm:imageUrl a owl:DatatypeProperty ;
        rdfs:label "Image URL" ;
        rdfs:comment "The image URL for the subject" ;
        rdfs:range xsd:string .

    # Migros Product URLs Property
    pfm:productUrls a owl:DatatypeProperty ;
        rdfs:label "Product URLs" ;
        rdfs:comment "The product URLs for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros Legal Designation Property
    pfm:legalDesignation a owl:DatatypeProperty ;
        rdfs:label "Legal Designation" ;
        rdfs:comment "The legal designation for a product" ;
        rdfs:domain pfm:Product ;
        rdfs:range xsd:string .

    # Migros Category Property
    pfm:category a owl:ObjectProperty ;
        rdfs:label "category" ;
        rdfs:comment "Links a product to its category" ;
        rdfs:domain pfm:Product ;
        rdfs:range pfm:ProductCategory .

    # Receipt ID Property
    pfm:receiptId a owl:DatatypeProperty ;
        rdfs:label "receipt ID" ;
        rdfs:comment "The identifier of a receipt" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range xsd:string .

    # Receipt Date Property
    pfm:receiptDate a owl:DatatypeProperty ;
        rdfs:label "receipt date" ;
        rdfs:comment "The date of a receipt" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range xsd:date .

    # Receipt Time Property
    pfm:receiptTime a owl:DatatypeProperty ;
        rdfs:label "receipt time" ;
        rdfs:comment "The time of a receipt" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range xsd:time .

    # VAT Number Property
    pfm:vatNumber a owl:DatatypeProperty ;
        rdfs:label "VAT number" ;
        rdfs:comment "The VAT number on a receipt" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range xsd:string .

    # Payment Method Property
    pfm:paymentMethod a owl:DatatypeProperty ;
        rdfs:label "payment method" ;
        rdfs:comment "The payment method used" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range xsd:string .

    # Authorization Code Property
    pfm:authorizationCode a owl:DatatypeProperty ;
        rdfs:label "authorization code" ;
        rdfs:comment "The authorization code for a transaction" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range xsd:string .

    # Entry Mode Property
    pfm:entryMode a owl:DatatypeProperty ;
        rdfs:label "entry mode" ;
        rdfs:comment "The entry mode for a card transaction" ;
        rdfs:domain pfm:Receipt ;
        rdfs:range xsd:string .

    # Item Description Property
    pfm:itemDescription a owl:DatatypeProperty ;
        rdfs:label "item description" ;
        rdfs:comment "The description of a line item" ;
        rdfs:domain pfm:ReceiptLineItem ;
        rdfs:range xsd:string .

    # Quantity Property
    pfm:quantity a owl:DatatypeProperty ;
        rdfs:label "quantity" ;
        rdfs:comment "The quantity of a line item" ;
        rdfs:domain pfm:ReceiptLineItem ;
        rdfs:range xsd:integer .

    # Line Subtotal Property
    pfm:lineSubtotal a owl:DatatypeProperty ;
        rdfs:label "line subtotal" ;
        rdfs:comment "The subtotal for a line item" ;
        rdfs:domain pfm:ReceiptLineItem ;
        rdfs:range xsd:decimal .

    # Exchange Rate Property
    pfm:exchangeRate a owl:DatatypeProperty ;
        rdfs:label "exchange rate" ;
        rdfs:comment "The exchange rate for a currency conversion" ;
        rdfs:domain pfm:CurrencyConversion ;
        rdfs:range xsd:decimal .

    # Conversion Date Property
    pfm:conversionDate a owl:DatatypeProperty ;
        rdfs:label "conversion date" ;
        rdfs:comment "The date of a currency conversion" ;
        rdfs:domain pfm:CurrencyConversion ;
        rdfs:range xsd:date .

    # =============================================================================
    # INDIVIDUALS - CURRENCIES
    # =============================================================================

    # Swiss Franc
    pfm:Swiss_franc a pfm:Currency ;
        rdfs:label "Swiss Franc" ;
        rdfs:comment "The currency of Switzerland" .

    # United States Dollar
    pfm:United_States_dollar a pfm:Currency ;
        rdfs:label "United States Dollar" ;
        rdfs:comment "The currency of the United States" .

    # Euro
    pfm:Euro a pfm:Currency ;
        rdfs:label "Euro" ;
        rdfs:comment "The currency of the European Union" .

    # =============================================================================
    # INDIVIDUALS - CARD SCHEME OPERATORS
    # =============================================================================

    # Visa Card Scheme Operator
    pfm:Visa a pfm:CardSchemeOperator ;
        rdfs:label "Visa" ;
        rdfs:comment "Visa payment card scheme operator" .

    # Mastercard Card Scheme Operator
    pfm:Mastercard a pfm:CardSchemeOperator ;
        rdfs:label "Mastercard" ;
        rdfs:comment "Mastercard payment card scheme operator" .

    # Maestro Card Scheme Operator
    pfm:Maestro a pfm:CardSchemeOperator ;
        rdfs:label "Maestro" ;
        rdfs:comment "Maestro payment card scheme operator" .

    # TWINT Card Scheme Operator
    pfm:TWINT a pfm:CardSchemeOperator ;
        rdfs:label "TWINT" ;
        rdfs:comment "TWINT payment card scheme operator" .

    # =============================================================================
    # INDIVIDUALS - PRODUCT CATEGORIES
    # =============================================================================

    # Alcohol Category
    pfm:Category_alcohol a pfm:ProductCategory ;
        rdfs:label "Wein, Bier & Spirituosen" ;
        rdfs:comment "Wine, beer and spirits" ;
        pfm:co2Factor 0.4000 ;
        pfm:taxClass "standard" .

    # Baby & Kids Category
    pfm:Category_baby_kids a pfm:ProductCategory ;
        rdfs:label "Baby & Kinder" ;
        rdfs:comment "Baby and children's products" ;
        pfm:co2Factor 0.9000 ;
        pfm:taxClass "standard" .

    # Beverages Category
    pfm:Category_beverages a pfm:ProductCategory ;
        rdfs:label "Getränke, Kaffee & Tee" ;
        rdfs:comment "Beverages, coffee and tea" ;
        pfm:co2Factor 0.3000 ;
        pfm:taxClass "standard" .

    # Bread & Bakery Category
    pfm:Category_bread_bakery a pfm:ProductCategory ;
        rdfs:label "Brot, Backwaren & Frühstück" ;
        rdfs:comment "Bread, bakery products and breakfast items" ;
        pfm:co2Factor 0.8000 ;
        pfm:taxClass "standard" .

    # Cleaning Category
    pfm:Category_cleaning a pfm:ProductCategory ;
        rdfs:label "Waschen & Putzen" ;
        rdfs:comment "Laundry and cleaning products" ;
        pfm:co2Factor 1.1000 ;
        pfm:taxClass "standard" .

    # Clothing & Accessories Category
    pfm:Category_clothing_accessories a pfm:ProductCategory ;
        rdfs:label "Bekleidung & Accessoires" ;
        rdfs:comment "Clothing and accessories" ;
        pfm:co2Factor 2.0000 ;
        pfm:taxClass "standard" .

    # Dairy & Eggs Category
    pfm:Category_dairy_eggs a pfm:ProductCategory ;
        rdfs:label "Milchprodukte, Eier & frische Fertiggerichte" ;
        rdfs:comment "Dairy products, eggs and fresh ready meals" ;
        pfm:co2Factor 1.2000 ;
        pfm:taxClass "standard" .

    # Drugstore & Cosmetics Category
    pfm:Category_drugstore_cosmetics a pfm:ProductCategory ;
        rdfs:label "Drogerie & Kosmetik" ;
        rdfs:comment "Drugstore and cosmetics" ;
        pfm:co2Factor 0.7000 ;
        pfm:taxClass "standard" .

    # Frozen Foods Category
    pfm:Category_frozen_foods a pfm:ProductCategory ;
        rdfs:label "Tiefkühlprodukte" ;
        rdfs:comment "Frozen foods" ;
        pfm:co2Factor 1.5000 ;
        pfm:taxClass "standard" .

    # Fruits & Vegetables Category
    pfm:Category_fruits_vegetables a pfm:ProductCategory ;
        rdfs:label "Früchte & Gemüse" ;
        rdfs:comment "Fresh fruits and vegetables" ;
        pfm:co2Factor 0.5000 ;
        pfm:taxClass "reduced" .

    # Household Category
    pfm:Category_household a pfm:ProductCategory ;
        rdfs:label "Haushalt & Wohnen" ;
        rdfs:comment "Household and home products" ;
        pfm:co2Factor 1.3000 ;
        pfm:taxClass "standard" .

    # Meat & Fish Category
    pfm:Category_meat_fish a pfm:ProductCategory ;
        rdfs:label "Fleisch & Fisch" ;
        rdfs:comment "Meat and fish products" ;
        pfm:co2Factor 2.5000 ;
        pfm:taxClass "standard" .

    # Pasta & Condiments Category
    pfm:Category_pasta_condiments a pfm:ProductCategory ;
        rdfs:label "Pasta, Würzmittel & Konserven" ;
        rdfs:comment "Pasta, condiments and canned goods" ;
        pfm:co2Factor 0.6000 ;
        pfm:taxClass "standard" .

    # Pet Supplies Category
    pfm:Category_pet_supplies a pfm:ProductCategory ;
        rdfs:label "Tierbedarf" ;
        rdfs:comment "Pet supplies" ;
        pfm:co2Factor 0.8000 ;
        pfm:taxClass "standard" .

    # Snacks Category
    pfm:Category_snacks a pfm:ProductCategory ;
        rdfs:label "Snacks" ;
        rdfs:comment "Snack foods and treats" ;
        pfm:co2Factor 1.0000 ;
        pfm:taxClass "standard" .

    # =============================================================================
    # INDIVIDUALS - MERCHANT CATEGORY SCHEME
    # =============================================================================

    # Merchant Category Scheme
    pfm:MerchantCategoryScheme a skos:ConceptScheme ;
        rdfs:label "Merchant Category Scheme" ;
        rdfs:comment "A scheme for classifying merchants into categories" .

    # =============================================================================
    # INDIVIDUALS - MERCHANT CATEGORIES (MCC)
    # =============================================================================

    # MCC 3015 - Airlines
    pfm:MCC_3015 a skos:Concept ;
        rdfs:label "Airlines" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 4111 - Transportation Services
    pfm:MCC_4111 a skos:Concept ;
        rdfs:label "Transportation Services" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 4112 - Railway Services
    pfm:MCC_4112 a skos:Concept ;
        rdfs:label "Railway Services" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 4900 - Utilities
    pfm:MCC_4900 a skos:Concept ;
        rdfs:label "Utilities" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 5411 - Grocery Stores
    pfm:MCC_5411 a skos:Concept ;
        rdfs:label "Grocery Stores" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 5541 - Gas Stations
    pfm:MCC_5541 a skos:Concept ;
        rdfs:label "Gas Stations" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 5691 - Men's and Women's Clothing Stores
    pfm:MCC_5691 a skos:Concept ;
        rdfs:label "Men's and Women's Clothing Stores" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 5812 - Eating Places and Restaurants
    pfm:MCC_5812 a skos:Concept ;
        rdfs:label "Eating Places and Restaurants" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 5814 - Fast Food Restaurants
    pfm:MCC_5814 a skos:Concept ;
        rdfs:label "Fast Food Restaurants" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 5999 - Miscellaneous and Specialty Retail Stores
    pfm:MCC_5999 a skos:Concept ;
        rdfs:label "Miscellaneous and Specialty Retail Stores" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 6012 - Financial Institutions
    pfm:MCC_6012 a skos:Concept ;
        rdfs:label "Financial Institutions" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 6513 - Real Estate Agents and Managers
    pfm:MCC_6513 a skos:Concept ;
        rdfs:label "Real Estate Agents and Managers" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 7999 - Amusement, Gambling, and Recreation
    pfm:MCC_7999 a skos:Concept ;
        rdfs:label "Amusement, Gambling, and Recreation" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # MCC 8299 - Schools and Educational Services
    pfm:MCC_8299 a skos:Concept ;
        rdfs:label "Schools and Educational Services" ;
        skos:inScheme pfm:MerchantCategoryScheme .

    # =============================================================================
    # PROPERTY RESTRICTIONS AND AXIOMS
    # =============================================================================

    # Transaction Status Values
    pfm:status rdfs:range [
        a owl:DataRange ;
        owl:oneOf (
            "settled"
            "pending"
            "rejected"
            "cancelled"
        )
    ] .

    # Transaction Type Values
    pfm:transactionType rdfs:range [
        a owl:DataRange ;
        owl:oneOf (
            "expense"
            "income"
            "transfer"
        )
    ] .

    # Card Status Values
    pfm:cardStatus rdfs:range [
        a owl:DataRange ;
        owl:oneOf (
            "active"
            "inactive"
            "blocked"
            "expired"
        )
    ] .

    # Card Type Values
    pfm:cardType rdfs:range [
        a owl:DataRange ;
        owl:oneOf (
            "debit"
            "credit"
            "prepaid"
        )
    ] .

    # Tax Class Values
    pfm:taxClass rdfs:range [
        a owl:DataRange ;
        owl:oneOf (
            "standard"
            "reduced"
            "zero"
            "exempt"
        )
    ] .

    # =============================================================================
    # FUNCTIONAL PROPERTIES
    # =============================================================================

    # Each card can only have one scheme operator
    pfm:cardSchemeOperator a owl:FunctionalProperty .

    # Each card can only be linked to one account
    pfm:linkedAccount a owl:FunctionalProperty .

    # Each merchant can only have one category
    pfm:merchantCategory a owl:FunctionalProperty .

    # Each transaction can only have one status
    pfm:status a owl:FunctionalProperty .

    # Each transaction can only have one type
    pfm:transactionType a owl:FunctionalProperty .

    # Each transaction can only have one value date
    pfm:valueDate a owl:FunctionalProperty .

    # Each card can only have one number
    pfm:cardNumber a owl:FunctionalProperty .

    # Each card can only have one status
    pfm:cardStatus a owl:FunctionalProperty .

    # Each card can only have one type
    pfm:cardType a owl:FunctionalProperty .

    # Each card can only have one expiry date
    pfm:expiryDate a owl:FunctionalProperty .

    # Each product category can only have one CO2 factor
    pfm:co2Factor a owl:FunctionalProperty .

    # Each product category can only have one tax class
    pfm:taxClass a owl:FunctionalProperty . 
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
