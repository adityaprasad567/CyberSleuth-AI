"""
Crime taxonomy for the cybercrime classifier.

Categories are aligned (loosely) with NCRP (National Cyber Crime Reporting
Portal) categories so real complaint data can later be mapped onto them.

Each category has:
- label: the class name used by the model
- legal_tags: which sections of law are typically relevant (used later to
  scope RAG retrieval - the classifier's output routes which legal chunks
  get retrieved, instead of searching the whole corpus)
- templates: sentence templates with {slots} for synthetic data generation
- slots: example fillers for each template placeholder
"""

# Rule-based safety recommendations and urgency flags per category.
# These are deterministic (not LLM-generated) so Feature 9/10 (safety recs,
# emergency alerts) work reliably even if the LLM reasoning layer is down or
# returns an empty list - the backend merges these with any LLM-generated
# recommendations rather than replacing them.
SAFETY_RECOMMENDATIONS = {
    "upi_fraud": [
        "Call your bank's helpline immediately and request to block/freeze the affected account.",
        "Report the transaction on the National Cybercrime Helpline 1930 as soon as possible.",
        "Do not click any further links claiming to help 'reverse' the transaction - these are frequently follow-up scams.",
        "Change your UPI PIN and app passwords from a different device if possible.",
    ],
    "phishing": [
        "Change the password of the affected account immediately, and any other account reusing that password.",
        "Enable multi-factor authentication (MFA) wherever available.",
        "Do not click any further links in messages claiming to be from the same sender.",
        "Check your account's recent login activity for unfamiliar sessions and log them out.",
    ],
    "otp_scam": [
        "Contact your bank immediately to freeze the account and report the unauthorized transaction.",
        "Report on the National Cybercrime Helpline 1930 immediately - speed matters for fund recovery.",
        "Never share an OTP over a call, even with someone claiming to be from your bank.",
        "Block your debit/credit card if it was linked to the affected account.",
    ],
    "fake_job_offer": [
        "Stop all further payments to the recruiter or company immediately.",
        "Preserve all chat/email evidence before the scammer can delete or block you.",
        "Verify any company's legitimacy independently before making further contact.",
    ],
    "investment_scam": [
        "Stop any further deposits into the platform immediately.",
        "Preserve screenshots of the app, transaction receipts, and all communication.",
        "Report to the National Cybercrime Helpline 1930 and consider informing SEBI if securities were involved.",
    ],
    "sextortion": [
        "Do not make any payment - payment rarely stops further threats and often increases them.",
        "Do not delete the threatening messages; preserve them as evidence.",
        "Report immediately on cybercrime.gov.in (has a dedicated confidential category for this) or call 1930.",
        "Consider limiting visibility of your social media profiles while the matter is being investigated.",
    ],
    "sim_swap": [
        "Contact your telecom provider immediately to check/block SIM porting on your number.",
        "Contact your bank to freeze the account and check for unauthorized transactions.",
        "Report to the National Cybercrime Helpline 1930 immediately.",
        "Change passwords for any account using this phone number for OTP-based recovery.",
    ],
}

URGENT_CATEGORIES = {"upi_fraud", "otp_scam", "sim_swap"}

# Below this, the classifier's top prediction is treated as unreliable (too
# close to chance level for a 7-way classification) - the urgent alert is
# suppressed and the caller is told to add more detail, rather than
# confidently declaring a crime type the model isn't actually sure of.
MIN_CONFIDENCE_THRESHOLD = 0.40

EMERGENCY_MESSAGE = (
    "This looks like it may involve active financial fraud. Every hour matters: "
    "call your bank's fraud helpline now to request a freeze, and call the National "
    "Cybercrime Helpline 1930 to report it immediately - prompt reporting significantly "
    "improves the chance of the funds being recovered or frozen before withdrawal."
)

# Feature 5: Complaint Completeness Checker.
# Per-category required fields, checked against what the user/evidence has
# provided. Kept as data here (not logic) - completeness.py in case_builder/
# implements how each field is actually checked.
REQUIRED_FIELDS = {
    "upi_fraud": ["description", "crime_type", "evidence", "transaction_id", "bank_name", "suspect_contact"],
    "phishing": ["description", "crime_type", "evidence", "suspect_contact"],
    "otp_scam": ["description", "crime_type", "evidence", "transaction_id", "bank_name", "suspect_contact"],
    "fake_job_offer": ["description", "crime_type", "evidence", "financial_loss", "suspect_contact"],
    "investment_scam": ["description", "crime_type", "evidence", "financial_loss", "suspect_contact"],
    "sextortion": ["description", "crime_type", "evidence", "suspect_contact"],
    "sim_swap": ["description", "crime_type", "evidence", "bank_name", "suspect_contact"],
}

FIELD_LABELS = {
    "description": "Description",
    "crime_type": "Crime Type (AI Detected)",
    "evidence": "Evidence (screenshot/file uploaded)",
    "transaction_id": "Transaction ID",
    "bank_name": "Bank Name / Platform",
    "financial_loss": "Financial Loss Amount",
    "suspect_contact": "Suspect Phone Number / UPI ID",
}

CATEGORIES = {
    "upi_fraud": {
        "legal_tags": ["it_act_66c", "it_act_66d", "bns_cheating", "npci_dispute"],
        "templates": [
            "Someone sent me a {link_type} link and after I clicked it, {amount} was debited from my {bank} account via UPI.",
            "I received a fake UPI collect request pretending to be from {sender} and lost {amount}.",
            "A scammer asked me to scan a QR code to 'receive' a refund, and instead {amount} got deducted from my account.",
            "My UPI PIN was never shared but {amount} was withdrawn after I clicked a link claiming to be from {sender}.",
        ],
        "slots": {
            "link_type": ["fake UPI", "KYC update", "cashback", "refund"],
            "amount": ["Rs 15,000", "Rs 3,200", "Rs 48,000", "Rs 900"],
            "bank": ["SBI", "HDFC", "ICICI", "Axis"],
            "sender": ["my electricity board", "Amazon support", "PhonePe support", "a bank official"],
        },
    },
    "phishing": {
        "legal_tags": ["it_act_66d", "it_act_66c", "bns_cheating"],
        "templates": [
            "I got an email pretending to be from {sender} asking me to log in and verify my account, and now my {account_type} is compromised.",
            "A message claiming to be {sender} asked for my login details through a fake website that looked identical to the real one.",
            "I entered my {account_type} password on a link sent via SMS that looked like it was from {sender}.",
        ],
        "slots": {
            "sender": ["my bank", "Income Tax Department", "Netflix", "my company IT team"],
            "account_type": ["email account", "net banking", "social media account", "company account"],
        },
    },
    "otp_scam": {
        "legal_tags": ["it_act_66c", "it_act_66d", "bns_cheating"],
        "templates": [
            "Someone called claiming to be from {bank} and asked for the OTP I received, after which {amount} was withdrawn.",
            "A caller pretending to be a {sender} representative convinced me to share my OTP, and money was deducted from my account.",
            "I received a call about a 'card block' issue and was tricked into sharing OTP, leading to a loss of {amount}.",
        ],
        "slots": {
            "bank": ["SBI", "HDFC", "ICICI", "Axis"],
            "amount": ["Rs 20,000", "Rs 5,500", "Rs 60,000"],
            "sender": ["bank", "credit card company", "insurance company"],
        },
    },
    "fake_job_offer": {
        "legal_tags": ["bns_cheating", "it_act_66d"],
        "templates": [
            "I was offered a work-from-home job by {sender} and asked to pay {amount} as a 'registration fee', after which they stopped responding.",
            "A recruiter contacted me on {platform} promising a high-paying job and asked for {amount} upfront for 'training material'.",
            "I paid {amount} to a company claiming to offer part-time data entry jobs found on {platform}, and now they are unreachable.",
        ],
        "slots": {
            "sender": ["a recruiter", "an HR agency", "a company called Bright Careers"],
            "amount": ["Rs 2,000", "Rs 10,000", "Rs 25,000"],
            "platform": ["WhatsApp", "Telegram", "a job portal", "Instagram"],
        },
    },
    "investment_scam": {
        "legal_tags": ["bns_cheating", "sebi_related", "it_act_66d"],
        "templates": [
            "I invested {amount} in a trading app recommended by {sender} that promised guaranteed high returns, and now I cannot withdraw my money.",
            "A group on {platform} convinced me to invest {amount} in cryptocurrency and the app stopped working after I deposited funds.",
            "Someone posing as a stock market expert on {platform} got me to invest {amount} through a fake trading platform.",
        ],
        "slots": {
            "sender": ["a Telegram group admin", "an 'advisor'", "a stranger on WhatsApp"],
            "amount": ["Rs 50,000", "Rs 1,20,000", "Rs 8,000"],
            "platform": ["Telegram", "WhatsApp", "Instagram"],
        },
    },
    "sextortion": {
        "legal_tags": ["it_act_66e", "bns_sexual_offense", "bns_cheating"],
        "templates": [
            "Someone recorded a video call with me and is now threatening to share it unless I pay {amount}.",
            "I was blackmailed with morphed images and asked to pay {amount} to prevent them being shared with my contacts.",
            "A person I met online is threatening to leak private photos unless I send {amount}.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "sim_swap": {
        "legal_tags": ["it_act_66c", "it_act_66d", "bns_cheating"],
        "templates": [
            "My phone suddenly lost network, and later I found {amount} was withdrawn from my bank account without any OTP prompt on my phone.",
            "My SIM was deactivated without my knowledge and my {bank} account was accessed and {amount} was transferred out.",
        ],
        "slots": {
            "amount": ["Rs 40,000", "Rs 75,000", "Rs 12,000"],
            "bank": ["SBI", "HDFC", "ICICI"],
        },
    },
}

LABELS = list(CATEGORIES.keys())
