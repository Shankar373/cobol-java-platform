# IBM MQ Semantics & Modernization Boundary
## Messaging APIs, Descriptors & Fail-Closed Strategy

---

## 1. Mainframe IBM MQ Architecture

IBM MQ provides enterprise asynchronous messaging on IBM z/OS:
- **Core APIs**: `MQCONN`, `MQCONNX`, `MQOPEN`, `MQPUT`, `MQPUT1`, `MQGET`, `MQINQ`, `MQSET`, `MQCLOSE`, `MQDISC`, `MQCMIT`, `MQBACK`.
- **Structures**: `MQMD` (Message Descriptor), `MQOD` (Object Descriptor), `MQPMO` (Put Message Options), `MQGMO` (Get Message Options).

---

## 2. Modernization Boundary & Fail-Closed Enforcement

- **Current Status**: `UNSUPPORTED / UNPROVEN`.
- **Enforcement**: Any call to `MQCONN`, `MQOPEN`, `MQPUT`, `MQGET`, `MQCLOSE`, `MQDISC`, `MQCMIT`, `MQBACK` emits:
  `diagnostic: construct="IMS_MQ", status="NATIVE_TRANSLATION_BLOCKED"`
- **Production Guidance**: For modernized Spring Boot architectures, map messaging to Spring JMS (`JmsTemplate`) or Spring Cloud Stream against Apache ActiveMQ Artemis or Apache Kafka.
