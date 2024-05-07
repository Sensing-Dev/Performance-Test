#include <exception>
#include <iostream>
#include "arv.h"

#include <string>
#include <iostream>
#include <sstream>
#include <vector>
#include <map>
#include <algorithm>
#include <regex>

#include <filesystem>
#include <iomanip>
#include <ctime>

#include <ion/ion.h>
#include <fstream>
#include <json/json.hpp>
#include "gendc_separator/ContainerHeader.h"
#include "gendc_separator/tools.h"

#define LOG_DISPLAY true

// The other PixelFormat values are https://www.emva.org/wp-content/uploads/GenICamPixelFormatValues.pdf
#define Mono8 0x01080001
#define Mono10 0x01100003
#define Mono12 0x01100005
#define RGB8 0x02180014
#define BGR8 0x02180015
#define BayerBG8 0x0108000B
#define BayerBG10 0x0110000F
#define BayerBG12 0x01100013

int getPixelFormatInInt(std::string pixelformat){
    if (pixelformat == "Mono8"){
        return Mono8;
    }else if (pixelformat == "Mono10"){
        return Mono10;
    }else if (pixelformat == "Mono12"){
        return Mono12;
    }else if (pixelformat == "RGB8"){
        return RGB8;
    }else if (pixelformat == "BGR8"){
        return BGR8;
    }else if (pixelformat == "BayerBG8"){
        return BayerBG8;
    }else if (pixelformat == "BayerBG10"){
        return BayerBG10;
    }else if (pixelformat == "BayerBG12"){
        return BayerBG12;
    }else{
        throw std::runtime_error(pixelformat + " is not supported as default in this tool.\nPlease update getPixelFormatInInt() ");
    }
}

int getByteDepth(int pfnc_pixelformat){
    if (pfnc_pixelformat == Mono8 || pfnc_pixelformat == RGB8 || pfnc_pixelformat == BGR8 || pfnc_pixelformat == BayerBG8){
        return 1;
    }else if (pfnc_pixelformat == Mono10 || pfnc_pixelformat == Mono12 || pfnc_pixelformat == BayerBG10 || pfnc_pixelformat == BayerBG12){
        return 2;
    }else{
        std::stringstream ss;
        ss << "0x" << std::hex << std::uppercase << pfnc_pixelformat << " is not supported as default in this tool.\nPlease update getByteDepth()";
        std::string hexString = ss.str();
        throw std::runtime_error(hexString);
    }
}

int getNumChannel(int pfnc_pixelformat){
    if (pfnc_pixelformat == Mono8 || pfnc_pixelformat == Mono10 || pfnc_pixelformat == Mono12 || 
        pfnc_pixelformat == BayerBG8 || pfnc_pixelformat == BayerBG10 || pfnc_pixelformat == BayerBG12){
        return 1;
    }else if (pfnc_pixelformat == RGB8 || pfnc_pixelformat == BGR8){
        return 3;
    }else{
        std::stringstream ss;
        ss << "0x" << std::hex << std::uppercase << pfnc_pixelformat << " is not supported as default in this tool.\nPlease update getNumChannel()";
        std::string hexString = ss.str();
        throw std::runtime_error(hexString);
    }
}

void logWrite(std::string log_type, std::string msg){
    if(LOG_DISPLAY){
        std::cout << "[LOG " << __FILE__ << "]" << "[" << log_type << "] " << msg << std::endl;
    }
}

template<typename... Args>
void logInfo(Args... args) {
    std::ostringstream oss;
    (oss << ... << args);
    logWrite("INFO", oss.str()) ;
}

template<typename... Args>
void logWarning(Args... args) {
    std::ostringstream oss;
    (oss << ... << args);
    logWrite("WARNING", oss.str()) ;
}

template<typename... Args>
void logStatus(Args... args) {
    std::ostringstream oss;
    (oss << ... << args);
    logWrite("STATUS", oss.str()) ;
}

template <class T>
class UserOption {
    T value_;
    std::vector<std::string> keys_;
    std::string description_;

    public:
        UserOption(T value, std::vector<std::string> keys, std::string description){
            value_ = value;
            keys_ = keys;
            description_ = description;
        }

        T getValue(){
            return value_;
        }

        void setValue(T value) {
            value_ = value;
        }

        bool ifOptionMatch(std::string option){
            for (std::string key : keys_){
                if (option == key){
                    return true;
                }
            }
            return false;
        }
    
    private:
        UserOption(){}
};

class DeviceInfo {
    private:
        // optional user input
        int number_of_devices_ = 1;

        // assume that all devices has the same values
        std::string operation_mode_ = "Came1USB1";
        bool gendc_streaming_mode_ = false;
        int width_ = 1;
        int height_ = 1;
        int payload_size_ = 1;
        std::string pixel_format_ = "RGB8";

        int num_devices_ = 1;

        GError *error = nullptr;
        
    public:
        DeviceInfo(int user_input_num_device = 1){
            arv_update_device_list ();
            int num_connected_device = static_cast<int>(arv_get_n_devices ());
            if (num_connected_device < 1){
                throw std::runtime_error("Device is not connected.");
            }

            const char* dev_id = arv_get_device_id (0);
            ArvDevice* device = arv_open_device(dev_id, nullptr);

            // determine the number of device to test 
            num_devices_ = user_input_num_device;
            if (arv_device_is_feature_available(device, "OperationMode", &error)){
                operation_mode_ = std::string(arv_device_get_string_feature_value(device, "OperationMode", &error));
                std::cout << operation_mode_ << std::endl;

                int expected_number_of_devices 
                    = operation_mode_ == "Came1USB1" ? 1
                    : operation_mode_ == "Came1USB2" ? 1
                    : operation_mode_ == "Came2USB2" ? 2
                    : operation_mode_ == "Came2USB2" ? 2 : 0;
                if (expected_number_of_devices != user_input_num_device){
                    logWarning("While OperationMode is set to " + operation_mode_ + ", the number of device is set to " + std::to_string(user_input_num_device));   
                }
                num_devices_ = expected_number_of_devices;
            }
            if (num_connected_device < num_devices_){
                g_object_unref (device);
                throw std::runtime_error("The user input -nd/--number-of-device is invalid.");
            }

            if (arv_device_is_feature_available(device, "GenDCDescriptor", &error)
                && arv_device_is_feature_available(device, "GenDCStreamingMode", &error)
                && std::strcmp(arv_device_get_string_feature_value(device, "GenDCStreamingMode", &error), "On") == 0
            ){
                gendc_streaming_mode_ = true;
            }

            width_ = static_cast<int>(arv_device_get_integer_feature_value(device, "Width", &error));
            height_ = static_cast<int>(arv_device_get_integer_feature_value(device, "Height", &error));
            payload_size_ = static_cast<int>(arv_device_get_integer_feature_value(device, "PayloadSize", &error));
            pixel_format_ = arv_device_get_string_feature_value(device, "PixelFormat", &error);

            g_object_unref (device);

            displayInfo();
        }

        std::string getPixelFormat(){
            return pixel_format_;
        }

        bool isGenDCMode(){
            return gendc_streaming_mode_;
        }

        int getNumDevice(){
            return num_devices_;
        }

        int getWidth(){
            return width_;
        }

        int getHeight(){
            return height_;
        }

        int getPayloadSize(){
            return payload_size_;
        }

    private:
        DeviceInfo(){}

        void displayInfo(){
            logInfo("OperationMode: ", operation_mode_);
            logInfo("Number of devices: ", num_devices_);
            logInfo("GenDCStreamingMode: ", gendc_streaming_mode_ ? "true" : "false");
            logInfo("Width: ", width_);
            logInfo("Height: ", height_);
            logInfo("PayloadSize: ", payload_size_);
            logInfo("PixelFormat: ", pixel_format_);
        }
};

class TestInfo {
    private:
        // optional user input
        std::string directory_;
        int number_of_frames_;
        int number_of_tests_;

        bool realtime_display_mode_;
        bool realtime_evaluation_mode_;
        bool delete_bins_;
        
    public:
        TestInfo(std::string directory, int num_frame, int num_test,
            bool realtime_display, bool realtime_evaluation, bool delete_bin
        ): directory_(directory), number_of_frames_(num_frame), number_of_tests_(num_test),
            realtime_display_mode_(realtime_display), realtime_evaluation_mode_(realtime_evaluation),
            delete_bins_(delete_bin)
        {
            displayInfo();
        }

    bool isRealtimeDisplayMode(){
        return realtime_display_mode_;
    }

    bool isRealtimeEvaluationMode(){
        return realtime_evaluation_mode_;
    }

    int getNumFrames(){
        return number_of_frames_;
    }

    private:
        TestInfo(){}

        void displayInfo(){
            logInfo("Saving Directory: ", directory_);
            logInfo("Number of frames: ", number_of_frames_);
            logInfo("Number of tests: ", number_of_tests_);
            logInfo("Realtime display mode: ", realtime_display_mode_ ? "true" : "false");
            logInfo("Realtime evaluation mode: ", realtime_evaluation_mode_ ? "true" : "false");
            logInfo("Delete bin files: ", delete_bins_ ? "true" : "false");
        }  
};

std::string getImageAcquisitionBB(bool gendc, std::string pixel_format){
    if (gendc){
        return "image_io_u3v_gendc";
    }

    if (pixel_format == "Mono8" || pixel_format == "BayerBG8" || pixel_format == "BayerRG8"){
        return "image_io_u3v_cameraN_u8x2";
    } else if (pixel_format == "Mono10" || pixel_format == "Mono12"
        || pixel_format == "BayerRG10" || pixel_format == "BayerRG12"
        || pixel_format == "BayerBG10" || pixel_format == "BayerBG12"){
        return "image_io_u3v_cameraN_u16x2";
    } else if (pixel_format == "RGB8" || pixel_format == "BGR8"){
        return "image_io_u3v_cameraN_u8x3";
    } else{
        throw std::runtime_error( pixel_format + " is currently not supported.");
    }
}

std::string getBinarySaverBB(bool gendc, std::string pixel_format){
    if (gendc){
        return "image_io_u3v_gendc";
    }
    
    if (pixel_format == "Mono8" || pixel_format == "BayerBG8" || pixel_format == "BayerRG8"){
        return "image_io_binarysaver_u8x2";
    } else if (pixel_format == "Mono10" || pixel_format == "Mono12"
        || pixel_format == "BayerRG10" || pixel_format == "BayerRG12"
        || pixel_format == "BayerBG10" || pixel_format == "BayerBG12"){
        return "image_io_binarysaver_u16x2";
    } else if (pixel_format == "RGB8" || pixel_format == "BGR8"){
        return "image_io_binarysaver_u8x3";
    } else{
        throw std::runtime_error( pixel_format + " is currently not supported.");
    }
}

int get_frame_size(nlohmann::json ith_sensor_config){
    int w = ith_sensor_config["width"];
    int h = ith_sensor_config["height"];
    int d = getByteDepth(ith_sensor_config["pfnc_pixelformat"]);
    int c = getNumChannel(ith_sensor_config["pfnc_pixelformat"]);
    return w * h * d * c;
}

const std::regex number_pattern(R"(\d+)");

int extractNumber(const std::string& filename) {
    std::smatch match;
    std::regex_search(filename, match, number_pattern);
    return std::stoi(match[0]);
}

void getFrameCountFromBin(std::string output_directory, std::map<int, std::vector<int>>& framecount_record){
    logStatus("Post recording Process... Framecount data is generated.");

    std::ifstream f(std::filesystem::path(output_directory) / std::filesystem::path("config.json"));
    nlohmann::json config = nlohmann::json::parse(f);

    std::vector<std::string> bin_files;
    for (const auto& entry : std::filesystem::directory_iterator(output_directory)) {
        if (entry.is_regular_file() && entry.path().extension() == ".bin") {
            bin_files.push_back(entry.path().filename().string());
        }
    }
    std::sort(bin_files.begin(), bin_files.end(), [](const std::string& a, const std::string& b) {
        return extractNumber(a) < extractNumber(b);
    });

    std::vector<int> frame_size;
    for (int i = 0; i < config["num_device"]; ++i){
        frame_size.push_back(get_frame_size(config["sensor"+std::to_string(i+1)]));
    }

    for (const auto& filename : bin_files){
        std::filesystem::path jth_bin= std::filesystem::path(output_directory) / std::filesystem::path(filename);

        if (!std::filesystem::exists(jth_bin)){
            throw std::runtime_error(filename + " does not exist");
        }

        std::ifstream ifs(jth_bin, std::ios::binary);
        if (!ifs.is_open()){
            throw std::runtime_error("Failed to open " + filename);
        }
        
        ifs.seekg(0, std::ios::end);
        std::streampos filesize = ifs.tellg();
        ifs.seekg(0, std::ios::beg);
        char* filecontent = new char[filesize];

        if (!ifs.read(filecontent, filesize)) {
            delete[] filecontent;
            throw std::runtime_error("Failed to open " + filename);
        }

        int cursor = 0;
        if (isGenDC(filecontent)){
            while(cursor < static_cast<int>(filesize)){
                for (int ith_device = 0; ith_device < config["num_device"]; ++ith_device){
                    ContainerHeader gendc_descriptor= ContainerHeader(filecontent + cursor);
                    std::tuple<int32_t, int32_t> data_comp_and_part = gendc_descriptor.getFirstAvailableDataOffset(true);
                    int offset = gendc_descriptor.getOffsetFromTypeSpecific(std::get<0>(data_comp_and_part), std::get<1>(data_comp_and_part), 3, 0);
                    framecount_record[ith_device].push_back(*reinterpret_cast<int*>(filecontent + cursor + offset));
                    cursor += gendc_descriptor.getDescriptorSize();
                }
            }
        }else{
            while(cursor < static_cast<int>(filesize)){
                for (int ith_device = 0; ith_device < config["num_device"]; ++ith_device){
                    framecount_record[ith_device].push_back(*reinterpret_cast<int*>(filecontent + cursor));
                    cursor += 4 + frame_size[ith_device];
                }
            }
        }
        delete[] filecontent;
    }
}

template<typename U>
void process_and_save(DeviceInfo& device_info, TestInfo& test_info, std::string output_directory_path_,
    std::map<int, std::vector<int>>& framecount_record){
    // pipeline setup
    ion::Builder b;
    b.set_target(ion::get_host_target());
    b.with_bb_module("ion-bb");

    // the first BB: Obtain GenDC/images
    ion::Node n = b.add(getImageAcquisitionBB(device_info.isGenDCMode(), device_info.getPixelFormat()))()
      .set_param(
        ion::Param("num_devices", device_info.getNumDevice()),
        ion::Param("frame_sync", true),
        ion::Param("realtime_diaplay_mode", test_info.isRealtimeDisplayMode())
      );

    // the second BB: optional
    if (test_info.isRealtimeEvaluationMode()){
        logStatus("Recording and evaluating Process... Framecount is stored during the record.");


        std::vector< int > buf_size = std::vector < int >{ device_info.getWidth(), device_info.getHeight() };
        if (device_info.getPixelFormat() == "RGB8"){
            buf_size.push_back(3);
        }
        std::vector<Halide::Buffer<U>> output;
        for (int i = 0; i < device_info.getNumDevice(); ++i){
        output.push_back(Halide::Buffer<U>(buf_size));
        }
        n["output"].bind(output);

        std::vector<Halide::Buffer<uint32_t>> fc;

        for (int i = 0; i < device_info.getNumDevice(); ++i){
            Halide::Buffer<uint32_t> frame_counts = Halide::Buffer<uint32_t>(device_info.getNumDevice());
            n["frame_count"][i].bind(frame_counts);
            fc.push_back(frame_counts);
        }
        
        for (int x = 0; x < test_info.getNumFrames(); ++x){
            b.run();
            for (int d = 0; d < device_info.getNumDevice(); ++d){
                framecount_record[d].push_back(fc[d](0));
            }
        }
        return;
    }else{
        logStatus("Recording Process... Bin files are generated.");

        if (device_info.isGenDCMode()){
            int payloadsize = device_info.getPayloadSize();
            n = b.add("image_io_binary_gendc_saver")(n["gendc"], n["device_info"], &payloadsize)
                .set_param(
                    ion::Param("num_devices", device_info.getNumDevice()),
                    ion::Param("output_directory", output_directory_path_),
                    ion::Param("input_gendc.size", device_info.getNumDevice()),
                    ion::Param("input_deviceinfo.size", device_info.getNumDevice())
                );
        }else{
            std::string bb_save_image = getBinarySaverBB(device_info.isGenDCMode(), device_info.getPixelFormat());
            int width = device_info.getWidth();
            int height = device_info.getHeight();
            if (device_info.getNumDevice() == 2){
                ion::Node coy_n = b.add(bb_save_image)(n["output"][1], n["device_info"][1], n["frame_count"][1], &width, &height)
                .set_param(
                    ion::Param("output_directory", output_directory_path_),
                    ion::Param("prefix", "sensor1-")
                );
                Halide::Buffer<int> cpy_terminator = Halide::Buffer<int>::make_scalar();
                coy_n["output"].bind(cpy_terminator);
            }
            n = b.add(bb_save_image)(n["output"][0], n["device_info"][0], n["frame_count"][0], &width, &height)
                .set_param(
                    ion::Param("output_directory", output_directory_path_),
                    ion::Param("prefix", "sensor0-")
                );
        }
        Halide::Buffer<int> terminator = Halide::Buffer<int>::make_scalar();
        n["output"].bind(terminator);

        for (int x = 0; x < test_info.getNumFrames(); ++x){
            b.run();
        }
        getFrameCountFromBin(output_directory_path_, framecount_record);
    }
}

void writeLog(std::string output_directory, DeviceInfo& device_info, std::map<int, std::vector<int>>& framecount_record){
    logStatus("Post Recording Process... A log for frameskip will be generated.");
    logInfo("log written in");

    std::vector<std::filesystem::path> logfile;
    std::vector<std::ofstream> ofs;

    for (int ith_device = 0; ith_device < framecount_record.size(); ++ith_device){
        logfile.push_back(std::filesystem::path(output_directory) / std::filesystem::path("camera-"+std::to_string(ith_device)+"-frame_log.txt"));
        ofs.push_back(std::ofstream(logfile[ith_device], std::ios::out));
        ofs[ith_device] << device_info.getWidth() << "x" << device_info.getHeight() << "\n";
        std::cout << "\t" << logfile[ith_device] << std::endl;
    }

    for (int ith_device = 0; ith_device < framecount_record.size(); ++ith_device){
        int num_dropped_frames = 0;
        int current_frame = 0;
        int offset_frame_count = 0;
        int expected_frame_count = 0;

        bool first_frame = true;
        for (int fc : framecount_record[ith_device]){
            if (first_frame){
                offset_frame_count = fc;
                expected_frame_count = fc;
                ofs[ith_device] << "offset_frame_count: " << fc << "\n";
            }

            bool frame_drop_occured = fc != expected_frame_count;

            if (frame_drop_occured){
                while (expected_frame_count < fc){
                    ofs[ith_device] << expected_frame_count << " : x\n";
                    num_dropped_frames += 1;
                    expected_frame_count += 1;
                }
            }

            frame_drop_occured = false;
            ofs[ith_device] << expected_frame_count << " : " << fc << "\n";
            expected_frame_count += 1;

            if (current_frame < fc){
                current_frame = fc;
            }
        }
        int total_num_frames = current_frame - offset_frame_count + 1;
        std::cout << "\t" << (total_num_frames-num_dropped_frames) * 1.0 / total_num_frames << std::endl;
    }
}


int main(int argc, char *argv[])
{
    UserOption<std::string> directory(".", std::vector<std::string>{"-d", "--directory"}, "Directory to save log");
    UserOption<int> num_device(1, std::vector<std::string>{"-nd", "--number-of-device"}, "The number of devices");
    UserOption<int> num_frame(100, std::vector<std::string>{"-nf", "--number-of-frames"}, "The number of frames to obtain per test");
    UserOption<int> num_test(2, std::vector<std::string>{"-nt", "--number-of-tests"}, "The number of tests to perform in this script");
    UserOption<bool> realtime_display(false, std::vector<std::string>{"-rt", "--realtime-display-mode"}, "Image capture in Realtime-display mode");
    UserOption<bool> realtime_evaluation(false, std::vector<std::string>{"-re", "--realtime-evaluation-mode"}, "Run performance test in Realtime-evaluation");
    UserOption<bool> delete_bin(false, std::vector<std::string>{"-db", "--delete-bins"}, "Delete bin files in --realtime-ecaluation-mode");

    if (argc > 1){
        for (int i = 1; i < argc; i++){
            std::string arg = argv[i];

            if (directory.ifOptionMatch(argv[i])){
                directory.setValue(argv[++i]);
            } else if (num_device.ifOptionMatch(argv[i])){
                num_device.setValue(std::stoi(argv[++i]));
            } else if (num_frame.ifOptionMatch(argv[i])){
                num_frame.setValue(std::stoi(argv[++i]));
            } else if (num_test.ifOptionMatch(argv[i])){
                num_test.setValue(std::stoi(argv[++i]));
            } else if (realtime_display.ifOptionMatch(argv[i])){
                realtime_display.setValue(true);
            } else if (realtime_evaluation.ifOptionMatch(argv[i])){
                realtime_evaluation.setValue(true);
            } else if (delete_bin.ifOptionMatch(argv[i])){
                delete_bin.setValue(true);
            }
        }
    }

    std::string saving_directory_prefix = "U3V-performance-test-";
    if (realtime_evaluation.getValue()){
        saving_directory_prefix += "without-saving-";
    }

    if (!std::filesystem::exists(directory.getValue())){
        std::filesystem::create_directory(directory.getValue());
    }
    std::time_t now;
    std::time(&now);
    std::tm tm;
    #ifdef _MSC_VER
    localtime_s(&tm, &now);
    #else
    &tm = std::localtime(&now);
    #endif
    std::stringstream ss;
    ss << saving_directory_prefix << std::put_time(&tm, "%Y-%m-%d-%H-%M-%S");
    std::filesystem::path saving_path = std::filesystem::path(directory.getValue()) / std::filesystem::path(ss.str());
    std::filesystem::create_directory(saving_path);

    DeviceInfo device_info(num_device.getValue());
    TestInfo test_info(directory.getValue(), num_frame.getValue(), num_test.getValue(),
        realtime_display.getValue(), realtime_evaluation.getValue(), delete_bin.getValue()
    );

    for (int i = 0; i < num_test.getValue(); ++i){
        std::filesystem::path ith_test_output_directory = saving_path / std::filesystem::path(std::to_string(i));
        std::filesystem::create_directory(ith_test_output_directory);

        std::map<int, std::vector<int>> framecount_record;
        for (int d = 0; d < device_info.getNumDevice(); ++d){
            framecount_record[d] = std::vector<int>();
        }
        if (device_info.getPixelFormat() == "Mono8" || device_info.getPixelFormat() == "RGB8"){
            process_and_save<uint8_t>(device_info, test_info, ith_test_output_directory.u8string(), framecount_record);
        }else{
            // std::cout << ith_test_output_directory << std::endl;
            process_and_save<uint16_t>(device_info, test_info, ith_test_output_directory.u8string(), framecount_record);
        }
        writeLog(ith_test_output_directory.u8string(), device_info, framecount_record);
        
    }

    

    return 0;
}