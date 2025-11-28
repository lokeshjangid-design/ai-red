import ssl
import socket
import os
import datetime
import ipaddress

def create_simple_ssl():
    """Create a simple self-signed certificate for local development"""
    try:
        # Create a simple self-signed certificate using Python's ssl module
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "MH"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Mumbai"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TrafficVision"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        # Build SAN with proper IP address objects
        san_names = [
            x509.DNSName("localhost"),
            x509.DNSName("192.168.1.11"),
        ]
        
        # Add IP address with proper format
        try:
            san_names.append(x509.IPAddress(ipaddress.IPv4Address("192.168.1.11")))
        except:
            pass  # Skip IP if fails
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.now(datetime.timezone.utc)
        ).not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName(san_names),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate files
        os.makedirs("../ssl", exist_ok=True)
        
        with open("../ssl/cert.pem", "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
        with open("../ssl/key.pem", "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        print("✅ SSL certificate created successfully!")
        print("Files: ../ssl/cert.pem, ../ssl/key.pem")
        print("Now you can access: https://192.168.1.11:5000")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    create_simple_ssl()
