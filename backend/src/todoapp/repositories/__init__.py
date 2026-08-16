"""Data access. One module per aggregate, plain SQL, no ORM.

Every function takes an open :class:`psycopg.AsyncConnection` as its first argument
so a service can compose several of them inside one transaction. Rows come back as
``dict``; converting them to proto messages is the service layer's job.
"""
