all: deploy

route53-ddns.zip: route53_ddns.py
	zip -9 route53-ddns.zip route53_ddns.py

route53-ddns-authorizer.zip: route53_ddns_authorizer.py
	zip -9 route53-ddns-authorizer.zip route53_ddns_authorizer.py

zip: route53-ddns.zip route53-ddns-authorizer.zip

deploy: route53-ddns.tf route53-ddns.zip route53-ddns-authorizer.zip
	terraform apply


clean:
	rm -f route53-ddns.zip route53-ddns-authorizer.zip

.PHONY: all clean deploy zip
