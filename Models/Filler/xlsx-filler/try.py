from excel_filler import ExcelFiller
#填写一下路径参数就可以使用了
filler = ExcelFiller(json_path=r"testrun/Docling-project/testSet002/inputJSON/data.JSON", input_folder=r"testrun/Docling-project/testSet002/input", output_folder=r"testrun/Docling-project/testSet002/out")
filler.run()