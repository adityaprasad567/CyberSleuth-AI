# """
# Crime taxonomy for the cybercrime classifier.

# Categories are aligned (loosely) with NCRP (National Cyber Crime Reporting
# Portal) categories so real complaint data can later be mapped onto them.

# Each category has:
# - label: the class name used by the model
# - legal_tags: which sections of law are typically relevant (used later to
#   scope RAG retrieval - the classifier's output routes which legal chunks
#   get retrieved, instead of searching the whole corpus)
# - templates: sentence templates with {slots} for synthetic data generation
# - slots: example fillers for each template placeholder
# """

# # Rule-based safety recommendations and urgency flags per category.
# # These are deterministic (not LLM-generated) so Feature 9/10 (safety recs,
# # emergency alerts) work reliably even if the LLM reasoning layer is down or
# # returns an empty list - the backend merges these with any LLM-generated
# # recommendations rather than replacing them.
# SAFETY_RECOMMENDATIONS = {
#     "upi_fraud": [
#         "Call your bank's helpline immediately and request to block/freeze the affected account.",
#         "Report the transaction on the National Cybercrime Helpline 1930 as soon as possible.",
#         "Do not click any further links claiming to help 'reverse' the transaction - these are frequently follow-up scams.",
#         "Change your UPI PIN and app passwords from a different device if possible.",
#     ],
#     "phishing": [
#         "Change the password of the affected account immediately, and any other account reusing that password.",
#         "Enable multi-factor authentication (MFA) wherever available.",
#         "Do not click any further links in messages claiming to be from the same sender.",
#         "Check your account's recent login activity for unfamiliar sessions and log them out.",
#     ],
#     "otp_scam": [
#         "Contact your bank immediately to freeze the account and report the unauthorized transaction.",
#         "Report on the National Cybercrime Helpline 1930 immediately - speed matters for fund recovery.",
#         "Never share an OTP over a call, even with someone claiming to be from your bank.",
#         "Block your debit/credit card if it was linked to the affected account.",
#     ],
#     "fake_job_offer": [
#         "Stop all further payments to the recruiter or company immediately.",
#         "Preserve all chat/email evidence before the scammer can delete or block you.",
#         "Verify any company's legitimacy independently before making further contact.",
#     ],
#     "investment_scam": [
#         "Stop any further deposits into the platform immediately.",
#         "Preserve screenshots of the app, transaction receipts, and all communication.",
#         "Report to the National Cybercrime Helpline 1930 and consider informing SEBI if securities were involved.",
#     ],
#     "sextortion": [
#         "Do not make any payment - payment rarely stops further threats and often increases them.",
#         "Do not delete the threatening messages; preserve them as evidence.",
#         "Report immediately on cybercrime.gov.in (has a dedicated confidential category for this) or call 1930.",
#         "Consider limiting visibility of your social media profiles while the matter is being investigated.",
#     ],
#     "sim_swap": [
#         "Contact your telecom provider immediately to check/block SIM porting on your number.",
#         "Contact your bank to freeze the account and check for unauthorized transactions.",
#         "Report to the National Cybercrime Helpline 1930 immediately.",
#         "Change passwords for any account using this phone number for OTP-based recovery.",
#     ],
# }

# URGENT_CATEGORIES = {"upi_fraud", "otp_scam", "sim_swap"}

# # Below this, the classifier's top prediction is treated as unreliable (too
# # close to chance level for a 7-way classification) - the urgent alert is
# # suppressed and the caller is told to add more detail, rather than
# # confidently declaring a crime type the model isn't actually sure of.
# MIN_CONFIDENCE_THRESHOLD = 0.40

# EMERGENCY_MESSAGE = (
#     "This looks like it may involve active financial fraud. Every hour matters: "
#     "call your bank's fraud helpline now to request a freeze, and call the National "
#     "Cybercrime Helpline 1930 to report it immediately - prompt reporting significantly "
#     "improves the chance of the funds being recovered or frozen before withdrawal."
# )

# # Feature 5: Complaint Completeness Checker.
# # Per-category required fields, checked against what the user/evidence has
# # provided. Kept as data here (not logic) - completeness.py in case_builder/
# # implements how each field is actually checked.
# REQUIRED_FIELDS = {
#     "upi_fraud": ["description", "crime_type", "evidence", "transaction_id", "bank_name", "suspect_contact"],
#     "phishing": ["description", "crime_type", "evidence", "suspect_contact"],
#     "otp_scam": ["description", "crime_type", "evidence", "transaction_id", "bank_name", "suspect_contact"],
#     "fake_job_offer": ["description", "crime_type", "evidence", "financial_loss", "suspect_contact"],
#     "investment_scam": ["description", "crime_type", "evidence", "financial_loss", "suspect_contact"],
#     "sextortion": ["description", "crime_type", "evidence", "suspect_contact"],
#     "sim_swap": ["description", "crime_type", "evidence", "bank_name", "suspect_contact"],
# }

# FIELD_LABELS = {
#     "description": "Description",
#     "crime_type": "Crime Type (AI Detected)",
#     "evidence": "Evidence (screenshot/file uploaded)",
#     "transaction_id": "Transaction ID",
#     "bank_name": "Bank Name / Platform",
#     "financial_loss": "Financial Loss Amount",
#     "suspect_contact": "Suspect Phone Number / UPI ID",
# }

# CATEGORIES = {
#     "upi_fraud": {
#         "legal_tags": ["it_act_66c", "it_act_66d", "bns_cheating", "npci_dispute"],
#         "templates": [
#             "Someone sent me a {link_type} link and after I clicked it, {amount} was debited from my {bank} account via UPI.",
#             "I received a fake UPI collect request pretending to be from {sender} and lost {amount}.",
#             "A scammer asked me to scan a QR code to 'receive' a refund, and instead {amount} got deducted from my account.",
#             "My UPI PIN was never shared but {amount} was withdrawn after I clicked a link claiming to be from {sender}.",
#         ],
#         "slots": {
#             "link_type": ["fake UPI", "KYC update", "cashback", "refund"],
#             "amount": ["Rs 15,000", "Rs 3,200", "Rs 48,000", "Rs 900"],
#             "bank": ["SBI", "HDFC", "ICICI", "Axis"],
#             "sender": ["my electricity board", "Amazon support", "PhonePe support", "a bank official"],
#         },
#     },
#     "phishing": {
#         "legal_tags": ["it_act_66d", "it_act_66c", "bns_cheating"],
#         "templates": [
#             "I got an email pretending to be from {sender} asking me to log in and verify my account, and now my {account_type} is compromised.",
#             "A message claiming to be {sender} asked for my login details through a fake website that looked identical to the real one.",
#             "I entered my {account_type} password on a link sent via SMS that looked like it was from {sender}.",
#         ],
#         "slots": {
#             "sender": ["my bank", "Income Tax Department", "Netflix", "my company IT team"],
#             "account_type": ["email account", "net banking", "social media account", "company account"],
#         },
#     },
#     "otp_scam": {
#         "legal_tags": ["it_act_66c", "it_act_66d", "bns_cheating"],
#         "templates": [
#             "Someone called claiming to be from {bank} and asked for the OTP I received, after which {amount} was withdrawn.",
#             "A caller pretending to be a {sender} representative convinced me to share my OTP, and money was deducted from my account.",
#             "I received a call about a 'card block' issue and was tricked into sharing OTP, leading to a loss of {amount}.",
#         ],
#         "slots": {
#             "bank": ["SBI", "HDFC", "ICICI", "Axis"],
#             "amount": ["Rs 20,000", "Rs 5,500", "Rs 60,000"],
#             "sender": ["bank", "credit card company", "insurance company"],
#         },
#     },
#     "fake_job_offer": {
#         "legal_tags": ["bns_cheating", "it_act_66d"],
#         "templates": [
#             "I was offered a work-from-home job by {sender} and asked to pay {amount} as a 'registration fee', after which they stopped responding.",
#             "A recruiter contacted me on {platform} promising a high-paying job and asked for {amount} upfront for 'training material'.",
#             "I paid {amount} to a company claiming to offer part-time data entry jobs found on {platform}, and now they are unreachable.",
#         ],
#         "slots": {
#             "sender": ["a recruiter", "an HR agency", "a company called Bright Careers"],
#             "amount": ["Rs 2,000", "Rs 10,000", "Rs 25,000"],
#             "platform": ["WhatsApp", "Telegram", "a job portal", "Instagram"],
#         },
#     },
#     "investment_scam": {
#         "legal_tags": ["bns_cheating", "sebi_related", "it_act_66d"],
#         "templates": [
#             "I invested {amount} in a trading app recommended by {sender} that promised guaranteed high returns, and now I cannot withdraw my money.",
#             "A group on {platform} convinced me to invest {amount} in cryptocurrency and the app stopped working after I deposited funds.",
#             "Someone posing as a stock market expert on {platform} got me to invest {amount} through a fake trading platform.",
#         ],
#         "slots": {
#             "sender": ["a Telegram group admin", "an 'advisor'", "a stranger on WhatsApp"],
#             "amount": ["Rs 50,000", "Rs 1,20,000", "Rs 8,000"],
#             "platform": ["Telegram", "WhatsApp", "Instagram"],
#         },
#     },
#     "sextortion": {
#         "legal_tags": ["it_act_66e", "bns_sexual_offense", "bns_cheating"],
#         "templates": [
#             "Someone recorded a video call with me and is now threatening to share it unless I pay {amount}.",
#             "I was blackmailed with morphed images and asked to pay {amount} to prevent them being shared with my contacts.",
#             "A person I met online is threatening to leak private photos unless I send {amount}.",
#         ],
#         "slots": {
#             "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
#         },
#     },
#     "sim_swap": {
#         "legal_tags": ["it_act_66c", "it_act_66d", "bns_cheating"],
#         "templates": [
#             "My phone suddenly lost network, and later I found {amount} was withdrawn from my bank account without any OTP prompt on my phone.",
#             "My SIM was deactivated without my knowledge and my {bank} account was accessed and {amount} was transferred out.",
#         ],
#         "slots": {
#             "amount": ["Rs 40,000", "Rs 75,000", "Rs 12,000"],
#             "bank": ["SBI", "HDFC", "ICICI"],
#         },
#     },
# }

# LABELS = list(CATEGORIES.keys())

"""
Crime taxonomy for the cybercrime classifier.

Categories are aligned (loosely) with NCRP (National Cyber Crime Reporting
Portal) categories so real complaint data can later be mapped onto them.
"""

SAFETY_RECOMMENDATIONS = {
    "upi_fraud": [
        "Call your bank's helpline immediately and request to block/freeze the affected account.",
        "Report the transaction on the National Cybercrime Helpline 1930 as soon as possible.",
        "Change your UPI PIN and app passwords from a different device if possible.",
    ],
    "phishing": [
        "Change the password of the affected account immediately, and any other account reusing that password.",
        "Enable multi-factor authentication (MFA) wherever available.",
    ],
    "otp_scam": [
        "Contact your bank immediately to freeze the account and report the unauthorized transaction.",
        "Report on the National Cybercrime Helpline 1930 immediately.",
    ],
    "ransomware": [
        "Disconnect the infected device from the network immediately to prevent spreading.",
        "Do not pay the ransom, as it does not guarantee data recovery.",
        "Report to the National Cybercrime Portal."
    ],
    "digital_arrest_scam": [
        "Disconnect the call immediately. Real law enforcement does not conduct interrogations over Skype.",
        "Do not transfer any 'security deposit'.",
        "Report the incident on the National Cybercrime Portal."
    ]
}

URGENT_CATEGORIES = {'aeps_fraud', 'sim_swap', 'upi_fraud', 'digital_arrest_scam', 'otp_scam', 'ransomware', 'customer_care_fraud'}

MIN_CONFIDENCE_THRESHOLD = 0.40

EMERGENCY_MESSAGE = (
    "This looks like it may involve active financial fraud. Every hour matters: "
    "call your bank's fraud helpline now to request a freeze, and call the National "
    "Cybercrime Helpline 1930 to report it immediately."
)

REQUIRED_FIELDS = {
    "otp_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "upi_fraud": ["description", "crime_type", "evidence", "suspect_contact"],
    "investment_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "sim_swap": ["description", "crime_type", "evidence", "suspect_contact"],
    "sextortion": ["description", "crime_type", "evidence", "suspect_contact"],
    "phishing": ["description", "crime_type", "evidence", "suspect_contact"],
    "fake_job_offer": ["description", "crime_type", "evidence", "suspect_contact"],
    "shopping_fraud": ["description", "crime_type", "evidence", "suspect_contact"],
    "identity_theft": ["description", "crime_type", "evidence", "suspect_contact"],
    "social_media_hacking": ["description", "crime_type", "evidence", "suspect_contact"],
    "email_hacking": ["description", "crime_type", "evidence", "suspect_contact"],
    "fake_customer_care": ["description", "crime_type", "evidence", "suspect_contact"],
    "loan_app_fraud": ["description", "crime_type", "evidence", "suspect_contact"],
    "digital_arrest_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "ransomware": ["description", "crime_type", "evidence", "suspect_contact"],
    "courier_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "electricity_bill_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "tech_support_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "ticket_booking_fraud": ["description", "crime_type", "evidence", "suspect_contact"],
    "rental_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "romance_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "crypto_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "insurance_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "charity_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "lottery_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "kyc_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "remote_access_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "credit_card_fraud": ["description", "crime_type", "evidence", "suspect_contact"],
    "pet_sale_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "telegram_marketplace_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "vehicle_sale_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "scholarship_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "subscription_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "travel_package_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "fastag_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "customs_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "event_ticket_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "aadhaar_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "matrimonial_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "gift_card_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "qr_code_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "deepfake_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "voice_clone_scam": ["description", "crime_type", "evidence", "suspect_contact"],
    "ai_impersonation": ["description", "crime_type", "evidence", "suspect_contact"],
    "fake_crypto_exchange": ["description", "crime_type", "evidence", "suspect_contact"],
    "apk_malware": ["description", "crime_type", "evidence", "suspect_contact"],
    "wifi_hacking": ["description", "crime_type", "evidence", "suspect_contact"],
    "data_breach": ["description", "crime_type", "evidence", "suspect_contact"],
    "unauthorized_network_access": ["description", "crime_type", "evidence", "suspect_contact"],
    "network_intrusion": ["description", "crime_type", "evidence", "suspect_contact"],
    "rogue_wifi_attack": ["description", "crime_type", "evidence", "suspect_contact"],
}


CATEGORIES = {
    "otp_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "Someone called claiming to be from HDFC and asked for the OTP I received, after which {amount} was withdrawn.",
            "Someone called claiming to be from HDFC and asked for the OTP I received, after which {amount} was withdrawn.",
            "Someone called claiming to be from HDFC and asked for the OTP I received, after which {amount} was withdrawn.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "upi_fraud": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I received a fake UPI collect request pretending to be from PhonePe support and lost {amount}.",
            "My UPI PIN was never shared but {amount} was withdrawn after I clicked a link claiming to be from Amazon support.",
            "Someone sent me a KYC update link and after I clicked it, {amount} was debited from my SBI account via UPI.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "investment_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "Someone posing as a stock market expert on Instagram got me to invest {amount} through a fake trading platform.",
            "Someone posing as a stock market expert on Telegram got me to invest {amount} through a fake trading platform.",
            "A group on Telegram convinced me to invest {amount} in cryptocurrency and the app stopped working after I deposited funds.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "sim_swap": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "My SIM was deactivated without my knowledge and my SBI account was accessed and {amount} was transferred out.",
            "My SIM was deactivated without my knowledge and my ICICI account was accessed and {amount} was transferred out.",
            "My SIM was deactivated without my knowledge and my HDFC account was accessed and {amount} was transferred out.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "sextortion": {
        "legal_tags": ["bns_extortion"],
        "templates": [
            "Someone recorded a video call with me and is now threatening to share it unless I pay {amount}.",
            "I was blackmailed with morphed images and asked to pay {amount} to prevent them being shared with my contacts.",
            "I was blackmailed with morphed images and asked to pay {amount} to prevent them being shared with my contacts.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "phishing": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I got an email pretending to be from my company IT team asking me to log in and verify my account, and now my email account is compromised.",
            "I entered my email account password on a link sent via SMS that looked like it was from my bank.",
            "A message claiming to be Netflix asked for my login details through a fake website that looked identical to the real one.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "fake_job_offer": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I paid {amount} to a company claiming to offer part-time data entry jobs found on Instagram, and now they are unreachable.",
            "A recruiter contacted me on a job portal promising a high-paying job and asked for {amount} upfront for 'training material'.",
            "I was offered a work-from-home job by a recruiter and asked to pay {amount} as a 'registration fee', after which they stopped responding.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "shopping_fraud": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I ordered a phone from Facebook Marketplace and paid online, but the seller stopped responding.",
            "I ordered a mobile phone from a shopping website and paid online, but the seller never shipped the product.",
            "I bought shoes from an Instagram store, made the payment through UPI, and the seller blocked me immediately.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "identity_theft": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "My Aadhaar details were used to open a loan without my knowledge.",
            "Someone created a bank account using my PAN card information.",
            "I discovered that my identity documents were used for fraudulent verification.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "social_media_hacking": {
        "legal_tags": ["it_act_66"],
        "templates": [
            "My Instagram account was hacked and all my photos were deleted.",
            "My Facebook account was taken over and scam messages were sent to my friends.",
            "I lost access to my X account after clicking a suspicious login link.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "email_hacking": {
        "legal_tags": ["it_act_66"],
        "templates": [
            "My Gmail account was hacked and confidential emails were deleted.",
            "My Outlook email password was changed without my permission.",
            "I cannot access my email because someone enabled two-factor authentication on my account.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "fake_customer_care": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake SBI customer care number asked me to install AnyDesk and stole money from my account.",
            "I searched Google for Flipkart customer care and called a fake support number that emptied my bank account.",
            "A fake Amazon support executive convinced me to share my screen using TeamViewer.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "loan_app_fraud": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I installed a loan app that accessed my contacts and started threatening me.",
            "A loan application demanded repayment even though I never received any loan.",
            "The fake loan app edited my photos and blackmailed me for more money.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "digital_arrest_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I received a video call from someone claiming to be a CBI officer who demanded money to avoid arrest.",
            "A fake police officer said my Aadhaar was linked to money laundering and asked me to transfer funds.",
            "I was told to stay on a video call while transferring money to verify my innocence.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "ransomware": {
        "legal_tags": ["bns_extortion"],
        "templates": [
            "My computer files were encrypted and the attacker demanded Bitcoin to unlock them.",
            "Every document on my laptop became inaccessible after opening an email attachment.",
            "I received a ransom note demanding cryptocurrency to recover my files.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "courier_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake courier message asked me to pay customs charges before delivering my parcel.",
            "I received an SMS saying my package was held at customs and I had to pay a fee.",
            "The delivery tracking website was fake and stole my payment details.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "electricity_bill_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "My electricity was supposedly going to be disconnected unless I paid through a link.",
            "I received an SMS asking me to update my electricity bill immediately or face disconnection.",
            "A fake electricity board employee convinced me to install a remote access app.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "tech_support_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fraudster pretending to be from Microsoft claimed my computer had viruses and asked me to install remote software.",
            "A fake Windows support engineer gained remote access to my laptop and stole banking details.",
            "The caller claimed my antivirus subscription had expired and charged me for fake renewal.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "ticket_booking_fraud": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I booked a flight ticket through a website offering huge discounts, but after payment the booking was never confirmed.",
            "I paid for train tickets through a fake travel portal and never received any ticket.",
            "The movie ticket booking website accepted my payment but didn't issue any tickets.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "rental_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I rented a flat after seeing an advertisement online and paid a security deposit, but the owner stopped answering calls.",
            "I transferred advance rent for an apartment listed on Facebook, but the property never existed.",
            "A fake landlord collected my booking amount and vanished.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "romance_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I met someone through a dating app who convinced me to send money for an emergency and then disappeared.",
            "My online partner claimed to be stranded abroad and requested financial help before blocking me.",
            "A person I met on Instagram developed a relationship with me only to ask for money.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "crypto_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I invested in a new cryptocurrency project that turned out to be fake.",
            "A crypto trading website showed fake profits but refused withdrawals.",
            "I lost my savings after investing in a fake Bitcoin mining platform.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "insurance_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake insurance agent collected premium payments without issuing any policy.",
            "I paid for vehicle insurance online but later discovered the policy number was fake.",
            "The insurance website accepted payment but never generated my policy document.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "charity_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake charity requested donations for flood victims and disappeared after collecting funds.",
            "I donated money to a fake NGO that was circulating messages on WhatsApp.",
            "A scammer created a fake crowdfunding page for a medical emergency.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "lottery_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I received an email claiming I had won an international lottery and had to pay processing fees.",
            "A message informed me that I won a lucky draw but requested taxes before releasing the prize.",
            "I transferred money to claim a luxury car prize that never existed.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "kyc_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake KYC update message redirected me to a phishing website.",
            "I received an SMS saying my bank account would be frozen unless I updated KYC immediately.",
            "The KYC verification link stole my banking credentials.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "remote_access_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I installed an app suggested by customer support and it remotely controlled my phone.",
            "A fraudster convinced me to install AnyDesk and accessed my banking application.",
            "The fake support executive used TeamViewer to steal my confidential information.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "credit_card_fraud": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "My debit card was used for online purchases without my permission.",
            "I noticed several unauthorized credit card transactions in my account statement.",
            "My card details were stolen after shopping on a suspicious website.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "pet_sale_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I paid an advance for a puppy advertised on Facebook, but the seller disappeared after receiving the money.",
            "I transferred money to buy a rare dog online, but the breeder blocked my number.",
            "I found a pet adoption website that collected payment but never delivered the animal.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "telegram_marketplace_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I paid for an iPhone advertised on Telegram but received a fake tracking number.",
            "The Telegram seller deleted the account after taking payment.",
            "I bought a gaming laptop through a Telegram channel and never received it.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "vehicle_sale_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I transferred money for a used car listed online, but the seller vanished.",
            "I paid a booking amount for a motorcycle advertised on OLX and lost my money.",
            "The seller provided fake vehicle registration documents before disappearing.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "scholarship_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake scholarship website collected my application fee and disappeared.",
            "I paid registration charges for an overseas scholarship that turned out to be fake.",
            "A fraudster promised guaranteed scholarship approval after receiving payment.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "subscription_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I received an email saying my subscription had expired and entered my card details.",
            "A fake Netflix renewal page charged my credit card without authorization.",
            "I clicked a fake Amazon Prime renewal link and lost money.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "travel_package_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I booked a holiday package through Instagram and the travel agency disappeared.",
            "I paid for an international tour package that never existed.",
            "A fake travel company accepted payment but never issued any travel documents.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "fastag_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I received an SMS claiming my FASTag would be blocked unless I paid immediately.",
            "I clicked a fake FASTag recharge link and lost {amount}.",
            "A fraudster pretending to be NHAI support collected money for FASTag activation.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "customs_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I paid a customs clearance fee for an international parcel that never existed.",
            "A fake customs officer demanded payment before releasing my package.",
            "I transferred money to clear imported goods that were never shipped.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "event_ticket_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake event organizer collected ticket money and cancelled the event.",
            "I purchased concert tickets from a fraudulent website.",
            "I paid for VIP passes through Instagram but never received them.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "aadhaar_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fraudster created a fake Aadhaar update portal and collected my personal details.",
            "I submitted my Aadhaar information on a fake government website.",
            "I paid money for Aadhaar correction services that never happened.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "matrimonial_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I created a profile on a matrimonial website and paid money to someone claiming to be interested in marriage, but they disappeared.",
            "A person I met on a matrimonial app kept asking for financial help and later blocked me.",
            "The bride's family demanded money for visa processing before marriage and vanished.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "gift_card_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fraudster convinced me to buy gift cards and shared the redemption codes, after which the balance disappeared.",
            "I was told to pay using Amazon gift cards for a refund process, but it was fraudulent.",
            "A fake Microsoft technician asked me to purchase gift cards to fix my computer.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "qr_code_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I scanned a QR code to receive money, but money was deducted instead.",
            "A fake QR code pasted over the original one redirected my payment.",
            "I received a QR code through WhatsApp claiming it would refund my order.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "deepfake_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I received a video call from my manager asking for money, but it was an AI-generated deepfake.",
            "A fake celebrity video convinced me to invest in cryptocurrency.",
            "I believed an AI-generated video promoting an investment platform and lost money.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "voice_clone_scam": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I received a phone call that sounded exactly like my son asking for emergency money, but it was AI-generated.",
            "The caller perfectly copied my friend's voice and requested an urgent bank transfer.",
            "I transferred money after hearing what I believed was my brother's voice.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "ai_impersonation": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "Someone created a fake profile pretending to be my company CEO and requested payments.",
            "A fraudster used AI-generated photos to impersonate a government officer.",
            "I received messages from an AI-generated fake profile asking for donations.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "fake_crypto_exchange": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "I deposited cryptocurrency into a fake exchange that later stopped working.",
            "The crypto exchange froze my account after I deposited funds.",
            "I transferred Bitcoin to a fraudulent trading platform.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "apk_malware": {
        "legal_tags": ["it_act_66"],
        "templates": [
            "I downloaded an APK from an unknown website and my banking app was compromised.",
            "A fake Android application stole my SMS messages and OTPs.",
            "I installed a modified APK that secretly accessed my contacts.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "wifi_hacking": {
        "legal_tags": ["it_act_66"],
        "templates": [
            "I connected to a public Wi-Fi network and later discovered unauthorized transactions.",
            "My email account was hacked after using free Wi-Fi at a café.",
            "I logged into internet banking over public Wi-Fi and my credentials were stolen.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "data_breach": {
        "legal_tags": ["it_act_66"],
        "templates": [
            "My company's customer database was leaked and my personal information became public.",
            "I received a notification that my email address was exposed in a major data breach.",
            "My passwords appeared on the internet after a company's servers were hacked.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "unauthorized_network_access": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "Someone gained unauthorized access to my office network and copied sensitive documents.",
            "I found unknown users connected to my company network without authorization.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "network_intrusion": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "The attacker bypassed network security and accessed our internal servers.",
            "My business network was compromised through an unsecured wireless connection.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
    "rogue_wifi_attack": {
        "legal_tags": ["bns_cheating"],
        "templates": [
            "A fake public Wi-Fi hotspot captured my login credentials.",
            "I connected to free airport Wi-Fi and later discovered unauthorized transactions from my bank account.",
            "The coffee shop Wi-Fi was fake and intercepted my passwords.",
        ],
        "slots": {
            "amount": ["Rs 10,000", "Rs 25,000", "Rs 5,000"],
        },
    },
}

LABELS = list(CATEGORIES.keys())