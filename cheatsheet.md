## View All Tables:
```
SELECT name FROM sqlite_master WHERE type='table';

Create a Table:
CREATE TABLE test (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER
);
```
## Insert Data:
```
INSERT INTO test (name, age) VALUES ('Alice', 25);
INSERT INTO test (name, age) VALUES ('Bob', 30);
```
## View All Records:
```
SELECT * FROM test;
```
## Update Data:
```
UPDATE test SET age = 26 WHERE name = 'Alice';
```
## Delete Data:
```
DELETE FROM test WHERE name = 'Bob';
```
## Drop a Table (Delete Table):
```
DROP TABLE test;
```
## Search for Data:
```
SELECT * FROM test WHERE age > 25;
SELECT * FROM test WHERE name LIKE 'A%';
```
## Count Rows:
```
SELECT COUNT(*) FROM test;
```
Sort Data:
SELECT * FROM test ORDER BY age ASC;
SELECT * FROM test ORDER BY age DESC;
