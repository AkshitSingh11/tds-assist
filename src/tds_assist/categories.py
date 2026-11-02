from enum import Enum


class Category(str, Enum):
    """Nature of payment. This is the only thing the LLM decides.

    The categories describe what the payment *is*, which did not change when the
    Income-tax Act 2025 replaced the 1961 Act. Section numbers, rates and payment
    codes did change, and live in rules.py keyed by date.
    """

    CONTRACT_WORK = "CONTRACT_WORK"
    PROFESSIONAL_FEES = "PROFESSIONAL_FEES"
    TECHNICAL_FEES = "TECHNICAL_FEES"
    DIRECTOR_FEES = "DIRECTOR_FEES"
    COMMISSION = "COMMISSION"
    RENT_LAND_BUILDING = "RENT_LAND_BUILDING"
    RENT_PLANT_MACHINERY = "RENT_PLANT_MACHINERY"
    GOODS_PURCHASE = "GOODS_PURCHASE"
    NEEDS_INFO = "NEEDS_INFO"


DESCRIPTIONS = {
    Category.CONTRACT_WORK: "Carrying out any work under a contract, including supply of labour, advertising, broadcasting, carriage of goods/passengers (not rail), catering, and manufacturing to the customer's specification using material bought from the customer.",
    Category.PROFESSIONAL_FEES: "Fees for professional services: legal, medical, engineering, architectural, accountancy, technical consultancy, interior decoration, advertising, or other notified professions.",
    Category.TECHNICAL_FEES: "Fees for technical services: managerial, technical or consultancy services (including provision of technical or other personnel), excluding construction/assembly/mining-type projects and salary.",
    Category.DIRECTOR_FEES: "Remuneration, fees or commission paid to a director of the company, other than salary.",
    Category.COMMISSION: "Commission or brokerage (not insurance commission) paid to a person acting on behalf of the company.",
    Category.RENT_LAND_BUILDING: "Rent for land, building, land appurtenant to a building, furniture or fittings.",
    Category.RENT_PLANT_MACHINERY: "Rent for the use of machinery, plant or equipment.",
    Category.GOODS_PURCHASE: "Purchase of goods (no service element), including standard goods bought off the shelf.",
    Category.NEEDS_INFO: "The invoice does not contain enough facts to choose between categories. Say which facts are missing.",
}
