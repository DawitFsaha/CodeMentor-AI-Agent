public class Main {
    public static void main(String[] args) {
        double x = 15.0;
        double y = 5.0;

        System.out.println("Addition: " + x + " + " + y + " = " + Add.calculate(x, y));
        System.out.println("Subtraction: " + x + " - " + y + " = " + Subtract.calculate(x, y));
        System.out.println("Multiplication: " + x + " * " + y + " = " + Multiply.calculate(x, y));
        System.out.println("Division: " + x + " / " + y + " = " + Divide.calculate(x, y));
    }
}