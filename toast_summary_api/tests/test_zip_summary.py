import unittest
import pandas as pd
from pandas.testing import assert_frame_equal
import zipfile
import tempfile
from pathlib import Path
from io import BytesIO

from toast_summary_api.toast_tool.zip_summary import summarize_toast_zip, VOID_THRESHOLD, DISCOUNT_THRESHOLD

class TestSummarizeToastZip(unittest.TestCase):
    def _create_zip_file(self, csv_name, csv_content):
        """Helper function to create a zip file with given csv content."""
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Create a nested structure similar to real Toast ZIPs
            # e.g., 2023-01-01/AllItemsReport.csv
            zf.writestr(f"2023-01-01/{csv_name}", csv_content)
        zip_buffer.seek(0)
        return zip_buffer.read()

    def test_valid_zip(self):
        csv_content = (
            "Date,Net Amount,Revenue Center,Check Number,Item Name\n"
            "2023-01-01,100.00,Food,1,Burger\n"
            "2023-01-01,50.00,Beverage,2,Soda\n"
            "2023-01-01,-10.00,Void Something,3,Voided Item\n" # Void
            "2023-01-01,-5.00,Discount 10%,4,Discount Applied\n" # Discount
            "2023-01-01,20.00,Food,1,Fries\n" # Same check number as first item
        )
        zip_bytes = self._create_zip_file("AllItemsReport.csv", csv_content)

        result_df = summarize_toast_zip(zip_bytes)

        expected_data = {
            "date": ["2023-01-01"],
            "net_sales": [100.00 + 50.00 - 10.00 - 5.00 + 20.00], # Sum of all Net Amounts
            "voids": [-10.00],
            "discounts": [-5.00],
            "orders": [3], # Check numbers 1, 2, 3, 4 (distinct)
            "flag_voids": [False], # -10 > 50 is False
            "flag_discounts": [False] # -5 > 50 is False
        }
        expected_df = pd.DataFrame(expected_data)
        # Round expected net_sales to 2 decimal places
        expected_df["net_sales"] = expected_df["net_sales"].round(2)

        assert_frame_equal(result_df, expected_df, check_dtype=False)

    def test_missing_columns(self):
        # Test case 1: Missing "Net Amount"
        csv_content_no_net_amount = (
            "Date,Revenue Center,Check Number,Item Name\n"
            "2023-01-01,Food,1,Burger\n"
            "2023-01-01,Beverage,2,Soda\n"
        )
        zip_bytes_no_net_amount = self._create_zip_file("AllItemsReport.csv", csv_content_no_net_amount)
        result_df_no_net_amount = summarize_toast_zip(zip_bytes_no_net_amount)
        expected_data_no_net_amount = {
            "date": ["2023-01-01"], "net_sales": [0], "voids": [0], "discounts": [0], "orders": [2],
            "flag_voids": [False], "flag_discounts": [False]
        }
        expected_df_no_net_amount = pd.DataFrame(expected_data_no_net_amount)
        assert_frame_equal(result_df_no_net_amount, expected_df_no_net_amount, check_dtype=False)

        # Test case 2: Missing "Revenue Center" (Net Amount is present)
        csv_content_no_revenue_center = (
            "Date,Net Amount,Check Number,Item Name\n"
            "2023-01-01,100.00,1,Burger\n"
            "2023-01-01,-10.00,2,Voided Item\n" # This would have been a void
        )
        zip_bytes_no_revenue_center = self._create_zip_file("AllItemsReport.csv", csv_content_no_revenue_center)
        result_df_no_revenue_center = summarize_toast_zip(zip_bytes_no_revenue_center)
        expected_data_no_revenue_center = {
            "date": ["2023-01-01"], "net_sales": [90.00], "voids": [0], "discounts": [0], "orders": [2],
            "flag_voids": [False], "flag_discounts": [False]
        }
        expected_df_no_revenue_center = pd.DataFrame(expected_data_no_revenue_center)
        assert_frame_equal(result_df_no_revenue_center, expected_df_no_revenue_center, check_dtype=False)

        # Test case 3: Missing "Check Number"
        csv_content_no_check_number = (
            "Date,Net Amount,Revenue Center,Item Name\n"
            "2023-01-01,100.00,Food,Burger\n"
            "2023-01-01,50.00,Beverage,Soda\n"
        )
        zip_bytes_no_check_number = self._create_zip_file("AllItemsReport.csv", csv_content_no_check_number)
        result_df_no_check_number = summarize_toast_zip(zip_bytes_no_check_number)
        expected_data_no_check_number = {
            "date": ["2023-01-01"], "net_sales": [150.00], "voids": [0], "discounts": [0], "orders": [0], # Orders is 0 as per requirement
            "flag_voids": [False], "flag_discounts": [False]
        }
        expected_df_no_check_number = pd.DataFrame(expected_data_no_check_number)
        assert_frame_equal(result_df_no_check_number, expected_df_no_check_number, check_dtype=False)

    def test_no_report_file(self):
        # Create a zip file with a differently named csv
        zip_bytes = self._create_zip_file("SomeOtherReport.csv", "col1,col2\nval1,val2")
        with self.assertRaisesRegex(FileNotFoundError, "No AllItemsReport.csv found in ZIP."):
            summarize_toast_zip(zip_bytes)

        # Create an empty zip file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            pass # No files added
        zip_buffer.seek(0)
        empty_zip_bytes = zip_buffer.read()
        with self.assertRaisesRegex(FileNotFoundError, "No AllItemsReport.csv found in ZIP."):
            summarize_toast_zip(empty_zip_bytes)

    def test_flags(self):
        # Test case 1: Voids and Discounts below threshold
        csv_content_below = (
            "Date,Net Amount,Revenue Center,Check Number\n"
            f"2023-01-01,{VOID_THRESHOLD - 1},Void,1\n"  # Voids = 49
            f"2023-01-01,{DISCOUNT_THRESHOLD -1},Discount,2\n" # Discounts = 49
        )
        zip_bytes_below = self._create_zip_file("AllItemsReport.csv", csv_content_below)
        result_df_below = summarize_toast_zip(zip_bytes_below)
        self.assertFalse(result_df_below["flag_voids"].iloc[0])
        self.assertFalse(result_df_below["flag_discounts"].iloc[0])
        self.assertEqual(result_df_below["voids"].iloc[0], VOID_THRESHOLD -1)
        self.assertEqual(result_df_below["discounts"].iloc[0], DISCOUNT_THRESHOLD -1)


        # Test case 2: Voids and Discounts equal to threshold (should be False, as it's strictly greater)
        csv_content_equal = (
            "Date,Net Amount,Revenue Center,Check Number\n"
            f"2023-01-01,{VOID_THRESHOLD},Void,1\n"
            f"2023-01-01,{DISCOUNT_THRESHOLD},Discount,2\n"
        )
        zip_bytes_equal = self._create_zip_file("AllItemsReport.csv", csv_content_equal)
        result_df_equal = summarize_toast_zip(zip_bytes_equal)
        self.assertFalse(result_df_equal["flag_voids"].iloc[0])
        self.assertFalse(result_df_equal["flag_discounts"].iloc[0])
        self.assertEqual(result_df_equal["voids"].iloc[0], VOID_THRESHOLD)
        self.assertEqual(result_df_equal["discounts"].iloc[0], DISCOUNT_THRESHOLD)


        # Test case 3: Voids and Discounts above threshold
        csv_content_above = (
            "Date,Net Amount,Revenue Center,Check Number\n"
            f"2023-01-01,{VOID_THRESHOLD + 1},Void,1\n"
            f"2023-01-01,{DISCOUNT_THRESHOLD + 1},Discount,2\n"
        )
        zip_bytes_above = self._create_zip_file("AllItemsReport.csv", csv_content_above)
        result_df_above = summarize_toast_zip(zip_bytes_above)
        self.assertTrue(result_df_above["flag_voids"].iloc[0])
        self.assertTrue(result_df_above["flag_discounts"].iloc[0])
        self.assertEqual(result_df_above["voids"].iloc[0], VOID_THRESHOLD + 1)
        self.assertEqual(result_df_above["discounts"].iloc[0], DISCOUNT_THRESHOLD + 1)

        # Test case 4: Voids above, Discounts below
        csv_content_mixed = (
            "Date,Net Amount,Revenue Center,Check Number\n"
            f"2023-01-01,{VOID_THRESHOLD + 10},Void,1\n"
            f"2023-01-01,{DISCOUNT_THRESHOLD - 10},Discount,2\n"
        )
        zip_bytes_mixed = self._create_zip_file("AllItemsReport.csv", csv_content_mixed)
        result_df_mixed = summarize_toast_zip(zip_bytes_mixed)
        self.assertTrue(result_df_mixed["flag_voids"].iloc[0])
        self.assertFalse(result_df_mixed["flag_discounts"].iloc[0])
        self.assertEqual(result_df_mixed["voids"].iloc[0], VOID_THRESHOLD + 10)
        self.assertEqual(result_df_mixed["discounts"].iloc[0], DISCOUNT_THRESHOLD - 10)


if __name__ == '__main__':
    unittest.main()
