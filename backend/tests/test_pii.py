from app.pii import redact


def test_email():

    text = (
        "Email: "
        "eshika@example.com"
    )

    result = redact(text)

    assert (
        "eshika@example.com"
        not in result
    )

    assert (
        "<PII:email_address>"
        in result
    )

def test_upi():

    text = "UPI: eshika@okhdfcbank"

    result = redact(text)

    assert "eshika@okhdfcbank" not in result

def test_phone():

    text = (
        "Phone: "
        "+91 9876543210"
    )

    result = redact(text)

    assert (
        "9876543210"
        not in result
    )

    assert (
        "<PII:phone_number>"
        in result
    )


def test_pan():

    text = "PAN: ABCDE1234F"

    result = redact(text)

    assert "ABCDE1234F" not in result


def test_aadhaar():

    text = (
        "Aadhaar: "
        "1234 5678 9012"
    )

    result = redact(text)

    assert (
        "1234 5678 9012"
        not in result
    )


def test_ifsc():

    text = (
        "IFSC: HDFC0001234"
    )

    result = redact(text)

    assert (
        "HDFC0001234"
        not in result
    )

    assert (
        "<PII:ifsc_code>"
        in result
    )


def test_account_number():

    text = "Account Number: 123456789012"

    result = redact(text)

    assert "123456789012" not in result

def test_masked_account():

    text = "A/C No: XXXXXXXX9012"

    result = redact(text)

    assert "XXXXXXXX9012" not in result

def test_customer_id():

    text = (
        "Customer ID: "
        "CUST123456"
    )

    result = redact(text)

    assert (
        "CUST123456"
        not in result
    )


def test_consistent_replacement():

    text = (
        "Email: "
        "eshika@example.com\n"
        "Alternate email: "
        "eshika@example.com"
    )

    result = redact(text)

    assert (
        result.count(
            "email_address_1"
        )
        == 2
    )

def test_card_number():

    text = "Card Number: 4111 1111 1111 1111"

    result = redact(text)

    assert "4111 1111 1111 1111" not in result

def test_transaction_amount_not_redacted():

    text = (
        "Transaction Amount: "
        "123456789"
    )

    result = redact(text)

    assert "123456789" in result

def test_transaction_reference_not_account():

    text = (
        "Transaction Reference: "
        "123456789012"
    )

    result = redact(text)

    assert "123456789012" in result

def test_email_not_upi():

    text = (
        "Email: "
        "eshika@gmail.com"
    )

    result = redact(text)

    assert "eshika@gmail.com" not in result

    assert "upi_id" not in result

def test_merchant_not_redacted():

    text = (
        "Merchant: Amazon"
    )

    result = redact(text)

    assert "Amazon" in result