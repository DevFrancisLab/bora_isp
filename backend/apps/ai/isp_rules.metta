; ISPBora decision rules.
; Python asserts (fact <name>) from database records, then runs each query.
; MeTTa returns decision symbols. Python executes them.
; balance-due is never asserted by ISPBora because billing balances are not stored.

!(match &self (fact customer-inactive) human-escalation-required)
!(match &self (fact service-inactive) human-escalation-required)
!(match &self (fact customer-active) (match &self (fact connection-offline) (match &self (fact diagnostics-not-run) troubleshooting-required)))
!(match &self (fact customer-active) (match &self (fact connection-degraded) troubleshooting-required))
!(match &self (fact customer-active) (match &self (fact connection-unknown) troubleshooting-required))
!(match &self (fact customer-active) (match &self (fact service-degraded) troubleshooting-required))
!(match &self (fact connection-online) (match &self (fact incident-active) troubleshooting-required))
!(match &self (fact connection-offline) (match &self (fact diagnostics-failed) technician-required))
!(match &self (fact service-outage) (match &self (fact connection-offline) technician-required))
!(match &self (fact service-outage) troubleshooting-required)
!(match &self (fact balance-due) billing-action-required)
!(match &self (fact connection-online) (match &self (fact diagnostics-success) service-appears-online))
