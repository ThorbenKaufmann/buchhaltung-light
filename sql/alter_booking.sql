
INSERT INTO skr03_accounts (id, name, default_tax, category, is_expense)
VALUES ('4980', 'Büromaterial / Werkzeuge', 19, 'Aufwand', TRUE);

ALTER TABLE booking_lines
    ADD CONSTRAINT booking_lines
        FOREIGN KEY (account_skr) REFERENCES skr03_accounts(id);

ALTER TABLE booking_rules
    ADD CONSTRAINT booking_rules
        FOREIGN KEY (default_account) REFERENCES skr03_accounts(id);
