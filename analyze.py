import pandas as pd

print("Reading Excel file...")
df = pd.read_excel('unique_companies_names.xlsx')

print(f"Original shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")

print("\n--- Unique Values per Column ---")
for col in df.columns:
    print(f"'{col}': {df[col].nunique()} unique values")

print("\nDropping fully duplicate rows...")
df_unique = df.drop_duplicates()
print(f"Rows after dropping duplicates: {df_unique.shape[0]}")

# Write to CSV
output_file = 'cleaned_companies.csv'
df_unique.to_csv(output_file, index=False)
print(f"\nWrote cleaned data to {output_file}")
