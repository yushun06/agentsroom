# Testing & Validation: [Feature/System Name]

## 1. Success Criteria
[What defines that this feature is 100% complete and working?]
*   Criterion 1: [e.g., API endpoint `/health` returns `200 OK`]
*   Criterion 2: [e.g., Data is successfully written to `output.json`]

## 2. Unit Tests Required
[List the specific functions or classes that require unit tests.]
*   `test_function_a.py`: Should verify [X, Y, Z]
*   `test_component_b.py`: Should verify [A, B]

## 3. Integration Tests / Manual Verification Steps
[If the agent needs to run an integration test or use a CLI tool to verify, list the exact commands here.]

### Verification Scenario 1: [Scenario Name]
1.  **Command to run:** `python src/main.py --input test.txt`
2.  **Expected Output:** The console should output `Success` and `result.txt` should be created.
3.  **Agent Action:** Read `result.txt` and verify it contains `Expected String`.

## 4. Known Regressions to Check
[List any previously broken features that this new code might impact, so the agent can double-check them.]
