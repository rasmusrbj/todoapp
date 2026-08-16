-- Runs once, the first time the Docker PostgreSQL volume is initialised.
--
-- The test suite drops and recreates its own database on every run, so all this has
-- to do is make sure the name exists for the very first connection.

CREATE DATABASE todoapp_test;
